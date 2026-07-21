from collections.abc import Generator
from datetime import date
import re

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..auth import active_user, require_trip_access
from ..models import Activity, ScheduledActivity, Trip, TripMember
from ..schemas import TripCreate, TripRead, TripUpdate
from ..services.collaboration import ensure_user_membership, new_share_code

router = APIRouter(prefix="/api/trips", tags=["trips"])


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for a trip request and close it afterward."""
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def optional_text(value: str | None) -> str | None:
    """Normalize optional form strings so blank values are stored as NULL."""
    if value is None:
        return None
    return value.strip() or None


@router.get("", response_model=list[TripRead])
def list_trips(database: Session = Depends(get_db)) -> list[Trip]:
    """Return only trips that belong to the signed-in user, newest first."""
    user = active_user()
    query = database.query(Trip).order_by(Trip.created_at.desc())
    if user:
        query = query.join(TripMember, TripMember.trip_id == Trip.id).filter(TripMember.user_id == user.id)
    return query.all()


@router.post("", response_model=TripRead, status_code=status.HTTP_201_CREATED)
def create_trip(payload: TripCreate, database: Session = Depends(get_db)) -> Trip:
    """Validate and persist a new trip before activity planning begins."""
    city = optional_text(payload.destination_city)
    region = optional_text(payload.destination_region)
    name = payload.name.strip()

    if not name:
        raise HTTPException(status_code=422, detail="Trip name is required.")
    if not city and not region:
        raise HTTPException(status_code=422, detail="Enter a destination city or region.")
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="End date cannot be before the start date.")

    user = active_user()
    trip = Trip(
        name=name,
        destination_city=city,
        destination_region=region,
        start_date=payload.start_date,
        end_date=payload.end_date,
        share_code=new_share_code(database),
        owner_user_id=user.id if user else None,
    )
    database.add(trip)
    database.flush()
    if user:
        ensure_user_membership(trip, user, database)
    database.commit()
    database.refresh(trip)
    return trip


@router.patch("/{trip_id}", response_model=TripRead)
def update_trip(trip_id: int, payload: TripUpdate, database: Session = Depends(get_db)) -> Trip:
    """Edit a trip without allowing its new dates to exclude scheduled activities."""
    trip = database.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")
    require_trip_access(trip, database)
    name = payload.name.strip()
    city = optional_text(payload.destination_city)
    region = optional_text(payload.destination_region)
    if not name:
        raise HTTPException(status_code=422, detail="Trip name is required.")
    if not city and not region:
        raise HTTPException(status_code=422, detail="Enter a destination city or region.")
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="End date cannot be before the start date.")
    outside_schedule = (
        database.query(ScheduledActivity)
        .join(Activity, Activity.id == ScheduledActivity.activity_id)
        .filter(
            Activity.trip_id == trip.id,
            (ScheduledActivity.scheduled_date < payload.start_date) | (ScheduledActivity.scheduled_date > payload.end_date),
        )
        .first()
    )
    if outside_schedule:
        raise HTTPException(status_code=422, detail="Move or unschedule activities outside the new travel dates before saving.")
    trip.name = name
    trip.destination_city = city
    trip.destination_region = region
    trip.start_date = payload.start_date
    trip.end_date = payload.end_date
    database.commit()
    database.refresh(trip)
    return trip


def pdf_text(value: str) -> str:
    """Escape text for a PDF content stream using its built-in Helvetica fonts."""
    return value.encode("cp1252", "replace").decode("cp1252").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap_pdf_text(value: str, max_characters: int) -> list[str]:
    """Wrap text conservatively for the fixed-width layout used in the export."""
    words = value.split()
    if not words:
        return []
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if line and len(candidate) > max_characters:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def build_itinerary_pdf(trip: Trip, records: list[tuple[Activity, ScheduledActivity]]) -> bytes:
    """Build a dependency-free, printable itinerary PDF with one section per trip day."""
    page_width, page_height = 612, 792  # US Letter in PostScript points.
    margin, footer_y = 48, 34
    pages: list[list[str]] = []
    commands: list[str] = []
    y = page_height - margin

    def add_page() -> None:
        nonlocal commands, y
        if commands:
            pages.append(commands)
        commands = []
        y = page_height - margin

    def text_line(content: str, x: float, font: str = "F1", size: float = 10, leading: float = 14, color: str = "0.15 0.20 0.19") -> None:
        nonlocal y
        commands.append(f"{color} rg BT /{font} {size} Tf {x} {y} Td ({pdf_text(content)}) Tj ET")
        y -= leading

    def require_space(height: float) -> None:
        if y - height < footer_y + 16:
            add_page()

    def day_header(day: date, day_number: int, following_height: float, continued: bool = False) -> None:
        nonlocal y
        require_space(49 + following_height)
        commands.append(f"0.15 0.20 0.19 rg {margin} {y - 34} {page_width - (margin * 2)} 34 re f")
        continuation = "  ·  CONTINUED" if continued else ""
        label = f"DAY {day_number}  |  {day.strftime('%A, %B')} {day.day}, {day.year}{continuation}"
        commands.append(f"1 1 1 rg BT /F2 12 Tf {margin + 14} {y - 21} Td ({pdf_text(label)}) Tj ET")
        y -= 49

    destination = ", ".join(item for item in [trip.destination_city, trip.destination_region] if item) or "Your trip"
    text_line("JETSETGO", margin, "F2", 9, 15, "0.88 0.38 0.31")
    text_line(trip.name, margin, "F2", 25, 31)
    text_line(f"{destination}  ·  {trip.start_date.strftime('%b')} {trip.start_date.day} – {trip.end_date.strftime('%b')} {trip.end_date.day}, {trip.end_date.year}", margin, "F1", 11, 26, "0.38 0.45 0.42")
    commands.append(f"0.85 0.88 0.85 RG {margin} {y + 8} m {page_width - margin} {y + 8} l S")
    y -= 15

    activities_by_day: dict[date, list[tuple[Activity, ScheduledActivity]]] = {}
    for activity, placement in records:
        activities_by_day.setdefault(placement.scheduled_date, []).append((activity, placement))

    current_day = trip.start_date
    day_number = 1
    while current_day <= trip.end_date:
        day_records = activities_by_day.get(current_day, [])
        if not day_records:
            day_header(current_day, day_number, 30)
            text_line("No stops planned yet.", margin + 14, "F1", 10, 30, "0.48 0.53 0.51")
        else:
            first_activity, _ = day_records[0]
            first_details = wrap_pdf_text(first_activity.address or "Location to be confirmed", 74)
            first_metadata = " · ".join(item for item in [first_activity.category, first_activity.estimated_cost] if item)
            first_block_height = 42 + (len(first_details) * 13) + (13 if first_metadata else 0)
            day_header(current_day, day_number, first_block_height)
        for stop_number, (activity, placement) in enumerate(day_records, 1):
            detail_lines = wrap_pdf_text(activity.address or "Location to be confirmed", 74)
            metadata = " · ".join(item for item in [activity.category, activity.estimated_cost] if item)
            block_height = 42 + (len(detail_lines) * 13) + (13 if metadata else 0)
            if y - block_height < footer_y + 16:
                add_page()
                day_header(current_day, day_number, block_height, continued=True)
            commands.append(f"0.91 0.95 0.93 rg {margin} {y - block_height + 5} {page_width - (margin * 2)} {block_height - 5} re f")
            time_label = placement.scheduled_time.strftime("%-I:%M %p") if placement.scheduled_time else "Flexible time"
            text_line(f"{stop_number:02d}  {time_label.upper()}", margin + 14, "F2", 8, 13, "0.44 0.53 0.49")
            text_line(activity.name, margin + 14, "F2", 13, 17)
            for line in detail_lines:
                text_line(line, margin + 14, "F1", 9.5, 13, "0.38 0.45 0.42")
            if metadata:
                text_line(metadata, margin + 14, "F1", 9, 13, "0.60 0.43 0.38")
            y -= 8
        current_day = date.fromordinal(current_day.toordinal() + 1)
        day_number += 1

    pages.append(commands)
    streams: list[bytes] = []
    for page_number, page in enumerate(pages, 1):
        footer = f"0.48 0.53 0.51 rg BT /F1 8 Tf {margin} {footer_y} Td (JetSetGo itinerary  |  Page {page_number} of {len(pages)}) Tj ET"
        streams.append(("\n".join(page + [footer]) + "\n").encode("cp1252", "replace"))

    objects: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    page_refs = " ".join(f"{5 + (index * 2)} 0 R" for index in range(len(streams)))
    objects.append(f"<< /Type /Pages /Kids [{page_refs}] /Count {len(streams)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    for index, stream in enumerate(streams):
        page_object = 5 + (index * 2)
        content_object = page_object + 1
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content_object} 0 R >>".encode())
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"endstream")

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, object_body in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode())
        pdf.extend(object_body)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode())
    return bytes(pdf)


@router.get("/{trip_id}/export/pdf")
def export_itinerary_pdf(trip_id: int, database: Session = Depends(get_db)) -> Response:
    """Download the itinerary as a day-by-day PDF."""
    trip = database.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found.")
    require_trip_access(trip, database)
    records = (
        database.query(Activity, ScheduledActivity)
        .join(ScheduledActivity, ScheduledActivity.activity_id == Activity.id)
        .filter(Activity.trip_id == trip.id)
        .order_by(ScheduledActivity.scheduled_date, ScheduledActivity.sort_order)
        .all()
    )
    filename = re.sub(r"[^a-z0-9]+", "-", trip.name.casefold()).strip("-") or "itinerary"
    return Response(
        content=build_itinerary_pdf(trip, records),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}-itinerary.pdf"'},
    )
