import { useEffect, useState } from 'react'
import AuthPage from './components/AuthPage'
import CreateTripPage from './pages/CreateTripPage'
import HomePage from './pages/HomePage'
import TripWorkspacePage from './pages/TripWorkspacePage'
import JoinTripModal from './components/JoinTripModal'
import ShareTripModal from './components/ShareTripModal'
import { useDisplayName } from './hooks/useDisplayName'
import { useAuthSession } from './hooks/useAuthSession'
import { useTripWorkspace } from './hooks/useTripWorkspace'
import { profileApi } from './services/api'

function App() {
  const { session, loading: authLoading, authenticate, signOut: endSession } = useAuthSession()
  const { displayName, saveDisplayName, clearDisplayName } = useDisplayName()
  const workspace = useTripWorkspace(displayName, Boolean(session), session?.access_token || '')
  const [page, setPage] = useState('home')
  const [shareOpen, setShareOpen] = useState(false)
  const [joinOpen, setJoinOpen] = useState(() => Boolean(new URLSearchParams(window.location.search).get('join')))
  const [joinCode, setJoinCode] = useState(() => new URLSearchParams(window.location.search).get('join') || '')

  useEffect(() => {
    const profileName = session?.user?.name
    if (profileName && !displayName) saveDisplayName(profileName)
  }, [displayName, saveDisplayName, session?.user?.name])

  if (authLoading) return <main className="grid min-h-screen place-items-center bg-[#f6f3ed] text-[#263230]"><p className="font-medium">Checking your session…</p></main>
  if (!session) return <AuthPage onAuthenticate={authenticate} />

  if (workspace.loading) return <main className="grid min-h-screen place-items-center bg-[#f6f3ed] text-[#263230]"><p className="font-medium">Loading your trips…</p></main>

  const createTrip = async (payload) => {
    const trip = await workspace.createTrip(payload)
    if (trip) setPage('workspace')
    return trip
  }

  const updateDisplayName = (value) => {
    saveDisplayName(value)
    profileApi.update(value).catch(() => {})
  }

  const signOut = async () => {
    await endSession()
    clearDisplayName()
    setPage('home')
  }

  if (page === 'create') return <CreateTripPage createTrip={createTrip} submitting={workspace.submitting} error={workspace.error} onBackHome={() => setPage('home')} />

  const joinTrip = async (payload) => {
    const result = await workspace.joinTrip(payload)
    if (!result) return null
    saveDisplayName(payload.display_name)
    setJoinOpen(false)
    setJoinCode('')
    window.history.replaceState({}, '', window.location.pathname)
    setPage('workspace')
    return result
  }

  if (page === 'workspace' && workspace.selectedTrip) return <><TripWorkspacePage workspace={workspace} displayName={displayName} onShare={() => setShareOpen(true)} onGoHome={() => setPage('home')} />{shareOpen && <ShareTripModal trip={workspace.selectedTrip} onClose={() => setShareOpen(false)} />}{joinOpen && <JoinTripModal initialCode={joinCode} displayName={displayName} onSaveDisplayName={saveDisplayName} onJoin={joinTrip} onClose={() => setJoinOpen(false)} submitting={workspace.submitting} error={workspace.error} />}</>

  return <><HomePage trips={workspace.trips} displayName={displayName} userEmail={session.user.username ? `@${session.user.username}` : ''} saveDisplayName={updateDisplayName} onCreateTrip={() => setPage('create')} onJoinTrip={() => setJoinOpen(true)} onSignOut={signOut} onOpenTrip={(tripId) => { workspace.selectTrip(tripId); setPage('workspace') }} />{joinOpen && <JoinTripModal initialCode={joinCode} displayName={displayName} onSaveDisplayName={updateDisplayName} onJoin={joinTrip} onClose={() => setJoinOpen(false)} submitting={workspace.submitting} error={workspace.error} />}</>
}

export default App
