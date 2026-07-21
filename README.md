# GetSetGOGO

GetSetGOGO is a collaborative travel-planning web app. It turns saved TikTok
ideas and manual entries into a shared collection of places, then helps groups
shape those places into practical day-by-day itineraries.

## Functionality

### Accounts and trips

- Create an account and sign in with a username and securely hashed password.
- Create, edit, and browse trips with a destination and required start/end
  dates.
- Persist users, trips, places, itinerary stops, memberships, and votes in
  PostgreSQL/Supabase.
- Show the signed-in profile, allow a display-name update, and sign out.

### Places and activity management

- Add places manually with an activity name, place/address, one or more fixed
  travel categories, an optional cost, and optional itinerary placement.
- Search Google Places for an address, then save the selected formatted address,
  coordinates, and regular opening hours.
- Create, edit, view in detail, filter, schedule, reorder, and delete places.
- Detect duplicate places using normalised activity names.
- Browse saved places by category and itinerary status (scheduled or unscheduled).

### TikTok and AI-assisted discovery

- Paste TikTok links, including share links that resolve to their canonical
  video URL.
- Retrieve video metadata and speech-to-text transcription through ScrapeBadger.
- Extract candidate activities from video captions and transcripts with Gemini.
- Continue extraction from metadata when a valid video has no detected speech.
- Review each extracted candidate before keeping or discarding it.
- Enrich saved activities with practical information grouped into food and
  consumption, visiting information, and vibe/context/highlights.

### Itinerary and maps

- Automatically expose every day in the trip date range as an itinerary day.
- Place approved activities using distance-based Google Routes data, while
  safely supporting an initially empty itinerary.
- Drag and drop stops to change their order.
- Display stop numbers, driving time, and distance between consecutive stops.
- Render the selected day on Google Maps with numbered markers and cached route
  polylines; selecting a marker or card keeps the views in sync.

### Collaboration and export

- Share a trip with an invitation code/link and display its member list.
- Join shared trips and vote on candidate places using the Group Pulse card.
- Export a day-by-day itinerary as a PDF.

## Technology

- Frontend: React, Vite, and Tailwind CSS.
- Backend: FastAPI, SQLAlchemy, and PostgreSQL/Supabase.
- Integrations: Google Maps Platform (Places API (New), Routes API, and Maps
  JavaScript API), ScrapeBadger, and Google Gemini.
- Deployment: separate Vercel frontend and FastAPI backend deployments.

## OpenAI use during development

OpenAI Codex was used as a development assistant to:

- plan and implement frontend and FastAPI features;
- review, debug, and improve API integrations, authentication, database
  migrations, CORS, and deployment configuration;
- generate and refine unit tests, error handling, and developer documentation;
- help identify configuration issues, such as browser-restricted Google keys
  being used for server-side Places requests.

All runtime requests are made directly by the application to its configured
services; no end-user trip, account, TikTok, or location data is sent to OpenAI
by the deployed app.
