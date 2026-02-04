import "@/index.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { Toaster } from "./components/ui/sonner";

// Pages
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Receitas from "./pages/Receitas";
import Despesas from "./pages/Despesas";
import Contratos from "./pages/Contratos";
import Pagamentos from "./pages/Pagamentos";
import Relatorios from "./pages/Relatorios";
import Configuracoes from "./pages/Configuracoes";
import AssinarContrato from "./pages/AssinarContrato";

// Protected Route Component
const ProtectedRoute = ({ children }) => {
    const { user, loading } = useAuth();
    
    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="animate-pulse text-muted-foreground">Carregando...</div>
            </div>
        );
    }
    
    if (!user) {
        return <Navigate to="/login" replace />;
    }
    
    return children;
};

// Public Route Component (redirects to dashboard if logged in)
const PublicRoute = ({ children }) => {
    const { user, loading } = useAuth();
    
    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="animate-pulse text-muted-foreground">Carregando...</div>
            </div>
        );
    }
    
    if (user) {
        return <Navigate to="/dashboard" replace />;
    }
    
    return children;
};

function AppRoutes() {
    return (
        <Routes>
            {/* Public Routes */}
            <Route path="/login" element={
                <PublicRoute>
                    <Login />
                </PublicRoute>
            } />
            <Route path="/register" element={
                <PublicRoute>
                    <Register />
                </PublicRoute>
            } />
            
            {/* Digital Signature Route (public - accessed via token) */}
            <Route path="/assinar/:token" element={<AssinarContrato />} />
            
            {/* Protected Routes */}
            <Route path="/dashboard" element={
                <ProtectedRoute>
                    <Dashboard />
                </ProtectedRoute>
            } />
            <Route path="/receitas" element={
                <ProtectedRoute>
                    <Receitas />
                </ProtectedRoute>
            } />
            <Route path="/despesas" element={
                <ProtectedRoute>
                    <Despesas />
                </ProtectedRoute>
            } />
            <Route path="/contratos" element={
                <ProtectedRoute>
                    <Contratos />
                </ProtectedRoute>
            } />
            <Route path="/pagamentos" element={
                <ProtectedRoute>
                    <Pagamentos />
                </ProtectedRoute>
            } />
            <Route path="/relatorios" element={
                <ProtectedRoute>
                    <Relatorios />
                </ProtectedRoute>
            } />
            <Route path="/configuracoes" element={
                <ProtectedRoute>
                    <Configuracoes />
                </ProtectedRoute>
            } />
            
            {/* Default redirect */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
    );
}

function App() {
    return (
        <BrowserRouter>
            <AuthProvider>
                <AppRoutes />
                <Toaster position="top-right" richColors />
            </AuthProvider>
        </BrowserRouter>
    );
}

export default App;
