import { useState } from 'react'
import { emptyTripForm } from '../utils/formatters'

export default function CreateTripPage({ createTrip, submitting, error, onBackHome }) {
  const [form, setForm] = useState(emptyTripForm)
  const update = (event) => setForm((current) => ({ ...current, [event.target.name]: event.target.value }))
  const submit = async (event) => {
    event.preventDefault()
    const trip = await createTrip(form)
    if (trip) setForm(emptyTripForm)
  }

  return <main className="min-h-screen bg-[#f6f3ed] px-5 py-8 text-[#263230] sm:px-10 sm:py-12"><button type="button" className="mx-auto mb-8 flex max-w-6xl items-center gap-2 text-sm font-semibold text-[#68716d] hover:text-[#263230]" onClick={onBackHome}>← All trips</button>
    <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1.15fr_.85fr] lg:items-center">
      <section className="order-2 lg:order-1">
        <p className="text-xs font-bold tracking-[.24em] text-[#e0604e]">JETSETGO</p>
        <h1 className="mt-5 max-w-xl font-serif text-5xl leading-[.98] tracking-[-.045em] text-[#263230] sm:text-7xl">A considered way to plan your next escape.</h1>
        <p className="mt-6 max-w-lg text-lg leading-8 text-[#68716d]">Build an itinerary from places you love, TikToks you save, and details that make each day run smoothly.</p>
        <div className="mt-10 grid max-w-lg grid-cols-3 gap-3 text-sm"><div className="rounded-2xl bg-[#e9e5db] p-4"><b className="block text-2xl">01</b><span className="text-[#68716d]">Save places</span></div><div className="rounded-2xl bg-[#dbe9e4] p-4"><b className="block text-2xl">02</b><span className="text-[#68716d]">Plan your days</span></div><div className="rounded-2xl bg-[#f4d9cf] p-4"><b className="block text-2xl">03</b><span className="text-[#68716d]">Travel hasslefree!</span></div></div>
      </section>
      <section className="order-1 rounded-[2rem] bg-[#263230] p-7 text-white shadow-[0_24px_70px_rgba(38,50,48,.16)] sm:p-10 lg:order-2">
        <p className="text-xs font-bold tracking-[.2em] text-[#f6b5a7]">NEW TRIP</p><h2 className="mt-3 font-serif text-3xl">Where are you headed?</h2>
        {error && <p className="mt-5 rounded-xl bg-[#583c39] px-4 py-3 text-sm text-[#ffe8e1]">{error}</p>}
        <form className="new-trip-form mt-8 grid gap-4" onSubmit={submit}>
          <label>Trip name<input name="name" value={form.name} onChange={update} required placeholder="e.g. Spring in Seoul" /></label>
          <div className="grid gap-4 sm:grid-cols-2"><label>City<input name="destination_city" value={form.destination_city} onChange={update} placeholder="Seoul" /></label><label>Region<input name="destination_region" value={form.destination_region} onChange={update} placeholder="South Korea" /></label></div>
          <div className="grid gap-4 sm:grid-cols-2"><label>Start date<input type="date" name="start_date" value={form.start_date} onChange={update} required /></label><label>End date<input type="date" name="end_date" value={form.end_date} onChange={update} required /></label></div>
          <button className="mt-3 rounded-xl bg-[#f19b87] px-5 py-3.5 font-bold text-[#263230] transition hover:bg-[#ffb3a0] disabled:opacity-60" disabled={submitting}>{submitting ? 'Creating…' : 'Create trip'}</button>
        </form>
      </section>
    </div>
  </main>
}
