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
import Assistente from "./pages/Assistente";

// Contador Portal Pages
import ContadorLogin from "./pages/ContadorLogin";
import ContadorDashboard from "./pages/ContadorDashboard";

// Conformidade TSE
import ConformidadeTSE from "./pages/ConformidadeTSE";

// Extratos Bancários
import ExtratosBancarios from "./pages/ExtratosBancarios";

// TSE Import
import { ImportarPrestacaoCont } from "./pages/ImportarPrestacaoCont";

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
            
            {/* Contador Portal Routes (Public Login, Protected Dashboard) */}
            <Route path="/contador/login" element={<ContadorLogin />} />
            <Route path="/contador/dashboard" element={<ContadorDashboard />} />
            
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
            <Route path="/assistente" element={
                <ProtectedRoute>
                    <Assistente />
                </ProtectedRoute>
            } />
            <Route path="/conformidade" element={
                <ProtectedRoute>
                    <ConformidadeTSE />
                </ProtectedRoute>
            } />
            <Route path="/extratos" element={
                <ProtectedRoute>
                    <ExtratosBancarios />
                </ProtectedRoute>
            } />
            <Route path="/importar-prestacao" element={
                <ProtectedRoute>
                    <ImportarPrestacaoCont />
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
