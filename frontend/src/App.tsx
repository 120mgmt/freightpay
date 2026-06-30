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
import ApiDocs from "./pages/ApiDocs.tsx";
import NotFound from "./pages/NotFound.tsx";
import VerifyEmail from "./pages/VerifyEmail.tsx";
import Payroll from "./pages/Payroll.tsx";
import Contractors from "./pages/Contractors.tsx";
import Bookkeeping from "./pages/Bookkeeping.tsx";
import Reports from "./pages/Reports.tsx";
import Billing from "./pages/Billing.tsx";

const queryClient = new QueryClient();

const protected_ = (el: React.ReactNode) => <ProtectedRoute>{el}</ProtectedRoute>;

const App = () => (
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <TooltipProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Index />} />
            <Route path="/signin" element={<SignIn />} />
            <Route path="/register" element={<Register />} />
            <Route path="/docs" element={<ApiDocs />} />
            <Route path="/verify-email" element={<VerifyEmail />} />
            <Route path="/dashboard"   element={protected_(<Dashboard />)} />
            <Route path="/payroll"     element={protected_(<Payroll />)} />
            <Route path="/settlements" element={protected_(<Contractors />)} />
            <Route path="/bookkeeping" element={protected_(<Bookkeeping />)} />
            <Route path="/reports"     element={protected_(<Reports />)} />
            <Route path="/billing"     element={protected_(<Billing />)} />
            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </AuthProvider>
  </QueryClientProvider>
);

export default App;
