import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import {
    LayoutDashboard,
    TrendingUp,
    TrendingDown,
    FileText,
    CreditCard,
    BarChart3,
    Settings,
    LogOut,
    Menu,
    X,
    ChevronRight,
    Vote,
    Bot
} from 'lucide-react';

const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { path: '/receitas', label: 'Receitas', icon: TrendingUp },
    { path: '/despesas', label: 'Despesas', icon: TrendingDown },
    { path: '/contratos', label: 'Contratos', icon: FileText },
    { path: '/pagamentos', label: 'Pagamentos', icon: CreditCard },
    { path: '/relatorios', label: 'Relatórios', icon: BarChart3 },
    { path: '/assistente', label: 'Assistente IA', icon: Bot, highlight: true },
    { path: '/configuracoes', label: 'Configurações', icon: Settings },
];

export const Layout = ({ children }) => {
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const { user, logout } = useAuth();
    const location = useLocation();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    return (
        <div className="min-h-screen bg-background" data-testid="app-layout">
            {/* Mobile header */}
            <header className="lg:hidden fixed top-0 left-0 right-0 z-50 glass border-b border-border/50 px-4 py-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setSidebarOpen(true)}
                            data-testid="mobile-menu-btn"
                        >
                            <Menu className="h-5 w-5" />
                        </Button>
                        <div className="flex items-center gap-2">
                            <Vote className="h-6 w-6 text-primary" />
                            <span className="font-heading font-bold text-lg">Eleitora 360</span>
                        </div>
                    </div>
                </div>
            </header>

            {/* Mobile sidebar overlay */}
            {sidebarOpen && (
                <div
                    className="lg:hidden fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            {/* Sidebar */}
            <aside
                className={`fixed top-0 left-0 z-50 h-full w-64 bg-card border-r border-border transform transition-transform duration-200 ease-out lg:translate-x-0 ${
                    sidebarOpen ? 'translate-x-0' : '-translate-x-full'
                }`}
                data-testid="sidebar"
            >
                <div className="flex flex-col h-full">
                    {/* Logo */}
                    <div className="flex items-center justify-between p-6 border-b border-border">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                                <Vote className="h-5 w-5 text-primary" />
                            </div>
                            <span className="font-heading font-bold text-xl">Eleitora 360</span>
                        </div>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="lg:hidden"
                            onClick={() => setSidebarOpen(false)}
                            data-testid="close-sidebar-btn"
                        >
                            <X className="h-5 w-5" />
                        </Button>
                    </div>

                    {/* Navigation */}
                    <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
                        {navItems.map((item) => {
                            const isActive = location.pathname === item.path;
                            const Icon = item.icon;
                            return (
                                <Link
                                    key={item.path}
                                    to={item.path}
                                    onClick={() => setSidebarOpen(false)}
                                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors duration-150 group ${
                                        isActive
                                            ? 'bg-primary text-primary-foreground'
                                            : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                                    }`}
                                    data-testid={`nav-${item.path.slice(1)}`}
                                >
                                    <Icon className="h-5 w-5" />
                                    <span className="font-medium">{item.label}</span>
                                    {isActive && (
                                        <ChevronRight className="h-4 w-4 ml-auto" />
                                    )}
                                </Link>
                            );
                        })}
                    </nav>

                    {/* User section */}
                    <div className="p-4 border-t border-border">
                        <div className="flex items-center gap-3 px-4 py-3 mb-2">
                            <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
                                <span className="text-sm font-semibold text-primary">
                                    {user?.name?.charAt(0)?.toUpperCase() || 'U'}
                                </span>
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="font-medium text-sm truncate">{user?.name}</p>
                                <p className="text-xs text-muted-foreground capitalize">{user?.role}</p>
                            </div>
                        </div>
                        <Button
                            variant="ghost"
                            className="w-full justify-start gap-3 text-muted-foreground hover:text-destructive"
                            onClick={handleLogout}
                            data-testid="logout-btn"
                        >
                            <LogOut className="h-5 w-5" />
                            <span>Sair</span>
                        </Button>
                    </div>
                </div>
            </aside>

            {/* Main content */}
            <main className="lg:pl-64 pt-16 lg:pt-0 min-h-screen">
                <div className="p-4 md:p-6 lg:p-8">
                    {children}
                </div>
            </main>
        </div>
    );
};
