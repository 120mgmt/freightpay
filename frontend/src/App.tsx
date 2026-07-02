import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import Index from "./pages/Index.tsx";
import SignIn from "./pages/SignIn.tsx";
import Register from "./pages/Register.tsx";
import Dashboard from "./pages/Dashboard.tsx";
import NotFound from "./pages/NotFound.tsx";
import VerifyEmail from "./pages/VerifyEmail.tsx";
import ForgotPassword from "./pages/ForgotPassword.tsx";
import ResetPassword from "./pages/ResetPassword.tsx";
import Payroll from "./pages/Payroll.tsx";
import Contractors from "./pages/Contractors.tsx";
import Bookkeeping from "./pages/Bookkeeping.tsx";
import Reports from "./pages/Reports.tsx";
import Billing from "./pages/Billing.tsx";
import Settings from "./pages/Settings.tsx";
import Terms from "./pages/Terms.tsx";
import Privacy from "./pages/Privacy.tsx";

const queryClient = new QueryClient();

const guard = (el: React.ReactNode) => <ProtectedRoute>{el}</ProtectedRoute>;

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            {/* Public */}
            <Route path="/" element={<Index />} />
            <Route path="/signin" element={<SignIn />} />
            <Route path="/register" element={<Register />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
            <Route path="/terms" element={<Terms />} />
            <Route path="/privacy" element={<Privacy />} />
            {/* Protected */}
            <Route path="/dashboard"   element={guard(<Dashboard />)} />
            <Route path="/payroll"     element={guard(<Payroll />)} />
            <Route path="/settlements" element={guard(<Contractors />)} />
            <Route path="/bookkeeping" element={guard(<Bookkeeping />)} />
            <Route path="/reports"     element={guard(<Reports />)} />
            <Route path="/billing"     element={guard(<Billing />)} />
            <Route path="/settings"    element={guard(<Settings />)} />
            {/* Catch-all */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
