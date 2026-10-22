import React from 'react';
import { ClerkProvider, SignIn, SignUp, SignedIn, SignedOut, RedirectToSignIn } from '@clerk/clerk-react';
import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Schemes from './components/Schemes';
import WhyUs from './components/WhyUs';
import Footer from './components/Footer';
import Dashboard from './components/Dashboard';
import OnboardingForm from './components/OnboardingForm';
import Profile from './components/Profile';
import Chat from './components/Chat';
import SchemeDirectory from './components/SchemeDirectory';
import SchemeDetails from './components/SchemeDetails';

import AuthenticatedNavbar from './components/AuthenticatedNavbar';

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

if (!PUBLISHABLE_KEY) {
  throw new Error("Missing Publishable Key")
}

const LandingPage = () => (
  <>
    <Navbar />
    <main>
      <Hero />
      <Schemes />
      <WhyUs />
    </main>
    <Footer />
  </>
);

// Linked from the navbar, but application tracking isn't built yet
const ApplicationsPlaceholder = () => (
  <div className="min-h-[calc(100vh-64px)] flex flex-col items-center justify-center bg-gray-50 px-4 text-center">
    <h1 className="text-2xl font-bold text-gray-900 mb-2">My Applications</h1>
    <p className="text-gray-500">Tracking your scheme applications is coming soon.</p>
  </div>
);

const NotFound = () => (
  <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 px-4 text-center">
    <h1 className="text-2xl font-bold text-gray-900 mb-2">Page not found</h1>
    <Link to="/" className="text-rose-500 font-semibold hover:text-rose-600">Go to the home page</Link>
  </div>
);

const ClerkProviderWithRoutes = () => {
  const navigate = useNavigate();

  return (
    <ClerkProvider
      publishableKey={PUBLISHABLE_KEY}
      navigate={(to) => navigate(to)}
      // Keep sign-in/up (and RedirectToSignIn) on the app's own routes instead of Clerk's hosted pages
      signInUrl="/sign-in"
      signUpUrl="/sign-up"
      appearance={{
        variables: {
          colorPrimary: '#f43f5e',
          colorTextOnPrimaryBackground: 'white',
        },
        elements: {
          card: 'shadow-xl border border-gray-100 rounded-2xl',
          formButtonPrimary: 'bg-rose-500 hover:bg-rose-600 text-white',
          footerActionLink: 'text-rose-500 hover:text-rose-600',
        }
      }}
    >
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route
          path="/sign-in/*"
          element={
            <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
              <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" />
            </div>
          }
        />
        <Route
          path="/sign-up/*"
          element={
            <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
              <SignUp 
                routing="path" 
                path="/sign-up" 
                signInUrl="/sign-in"
                forceRedirectUrl="/onboarding"
              />
            </div>
          }
        />
        <Route
          path="/onboarding"
          element={
            <>
              <SignedIn>
                <OnboardingForm />
              </SignedIn>
              <SignedOut>
                <RedirectToSignIn />
              </SignedOut>
            </>
          }
        />
        <Route
          path="/dashboard"
          element={
            <>
              <SignedIn>
                <AuthenticatedNavbar />
                <Dashboard />
              </SignedIn>
              <SignedOut>
                <RedirectToSignIn />
              </SignedOut>
            </>
          }
        />
        <Route
          path="/profile"
          element={
            <>
              <SignedIn>
                <AuthenticatedNavbar />
                <Profile />
              </SignedIn>
              <SignedOut>
                <RedirectToSignIn />
              </SignedOut>
            </>
          }
        />
        <Route
          path="/chat"
          element={
            <>
              <SignedIn>
                <AuthenticatedNavbar />
                <Chat />
              </SignedIn>
              <SignedOut>
                <RedirectToSignIn />
              </SignedOut>
            </>
          }
        />
        <Route
          path="/schemes"
          element={
            <>
              <SignedIn>
                <AuthenticatedNavbar />
                <SchemeDirectory />
              </SignedIn>
              <SignedOut>
                <RedirectToSignIn />
              </SignedOut>
            </>
          }
        />
        <Route
          path="/schemes/:slug"
          element={
            <>
              <SignedIn>
                <AuthenticatedNavbar />
                <SchemeDetails />
              </SignedIn>
              <SignedOut>
                <RedirectToSignIn />
              </SignedOut>
            </>
          }
        />
        <Route
          path="/applications"
          element={
            <>
              <SignedIn>
                <AuthenticatedNavbar />
                <ApplicationsPlaceholder />
              </SignedIn>
              <SignedOut>
                <RedirectToSignIn />
              </SignedOut>
            </>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </ClerkProvider>
  );
};

function App() {
  return (
    <BrowserRouter>
      <ClerkProviderWithRoutes />
    </BrowserRouter>
  );
}

export default App;
