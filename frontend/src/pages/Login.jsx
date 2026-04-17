import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { AtivaBrand } from '../components/AtivaBrand';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { Eye, EyeOff, ArrowRight } from 'lucide-react';
import { getErrorMessage } from '../lib/utils';

export default function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);

        try {
            await login(email, password);
            toast.success('Login realizado com sucesso!');
            navigate('/dashboard');
        } catch (error) {
            toast.error(getErrorMessage(error, 'Erro ao fazer login'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex" data-testid="login-page">
            <div className="flex-1 flex items-center justify-center p-8">
                <div className="w-full max-w-md animate-fade-in-up">
                    <AtivaBrand className="mb-8" />

                    <Card className="border-border/80 bg-white/90 shadow-[0_24px_60px_rgba(15,23,42,0.08)]">
                        <CardHeader className="space-y-1">
                            <CardTitle className="font-heading text-2xl">Entrar</CardTitle>
                            <CardDescription>
                                Digite suas credenciais para acessar a plataforma
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={handleSubmit} className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="email">Email</Label>
                                    <Input
                                        id="email"
                                        type="email"
                                        placeholder="seu@email.com"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        required
                                        className="h-12"
                                        data-testid="login-email-input"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="password">Senha</Label>
                                    <div className="relative">
                                        <Input
                                            id="password"
                                            type={showPassword ? 'text' : 'password'}
                                            placeholder="••••••••"
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            required
                                            className="h-12 pr-10"
                                            data-testid="login-password-input"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowPassword(!showPassword)}
                                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                                        >
                                            {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                                        </button>
                                    </div>
                                </div>
                                <Button
                                    type="submit"
                                    className="w-full h-12 font-semibold gap-2"
                                    disabled={loading}
                                    data-testid="login-submit-btn"
                                >
                                    {loading ? 'Entrando...' : 'Entrar'}
                                    {!loading && <ArrowRight className="h-4 w-4" />}
                                </Button>
                            </form>

                            <div className="mt-6 text-center space-y-2">
                                <p className="text-sm text-muted-foreground">
                                    Não tem uma conta?{' '}
                                    <Link
                                        to="/register"
                                        className="text-primary hover:underline font-medium"
                                        data-testid="register-link"
                                    >
                                        Cadastre-se
                                    </Link>
                                </p>
                                <p className="text-sm text-muted-foreground">
                                    <Link
                                        to="/contador/login"
                                        className="text-emerald-600 hover:underline font-medium"
                                        data-testid="contador-login-link"
                                    >
                                        Acesso para Contadores
                                    </Link>
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>

            <div className="hidden lg:flex flex-1 relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-primary/15 via-transparent to-secondary/20" />
                <img
                    src="https://images.unsplash.com/photo-1551288049-bebda4e38f71?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxOTJ8MHwxfHNlYXJjaHwzfHxhYnN0cmFjdCUyMGZpbmFuY2lhbCUyMGRhdGElMjB2aXN1YWxpemF0aW9uJTIwZGFyayUyMGJhY2tncm91bmR8ZW58MHx8fHwxNzY4OTI4NzUxfDA&ixlib=rb-4.1.0&q=85"
                    alt="Painel financeiro"
                    className="w-full h-full object-cover opacity-60"
                />
                <div className="absolute inset-0 flex items-center justify-center p-12">
                    <div className="max-w-lg rounded-[2rem] border border-white/50 bg-white/65 p-10 text-slate-900 shadow-[0_24px_80px_rgba(15,23,42,0.14)] backdrop-blur-xl">
                        <p className="mb-4 text-sm font-semibold uppercase tracking-[0.28em] text-primary">
                            Flora + Operação
                        </p>
                        <h2 className="font-heading text-4xl font-bold mb-4">
                            Governança eleitoral
                            <br />
                            com clareza
                        </h2>
                        <p className="text-lg text-slate-600">
                            Controle financeiro, contratos, conformidade e a Flora em uma única operação.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
}
