import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { Calculator, Eye, EyeOff, ArrowRight, Building2 } from 'lucide-react';
import axios from 'axios';
import { getErrorMessage } from '../lib/utils';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function ContadorLogin() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);

        try {
            const response = await axios.post(`${API_URL}/api/admin/contador/login`, {
                email,
                password
            });

            localStorage.setItem('contador_token', response.data.token);
            localStorage.setItem('contador_user', JSON.stringify(response.data.professional));
            localStorage.setItem('contador_is_admin', response.data.is_admin);

            toast.success('Login realizado com sucesso!');
            navigate('/contador/dashboard');
        } catch (error) {
            toast.error(getErrorMessage(error, 'Credenciais inválidas'));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex" data-testid="contador-login-page">
            {/* Left side - Form */}
            <div className="flex-1 flex items-center justify-center p-8 bg-gradient-to-br from-background to-muted/30">
                <div className="w-full max-w-md animate-fade-in-up">
                    <div className="flex items-center gap-3 mb-8">
                        <div className="w-14 h-14 rounded-xl bg-emerald-500/20 flex items-center justify-center">
                            <Building2 className="h-7 w-7 text-emerald-500" />
                        </div>
                        <div>
                            <h1 className="font-heading text-2xl font-bold">Ativa Contabilidade</h1>
                            <p className="text-sm text-muted-foreground">Portal do Contador</p>
                        </div>
                    </div>

                    <Card className="border-border bg-card shadow-xl">
                        <CardHeader className="space-y-1">
                            <CardTitle className="font-heading text-2xl">Acesso Contador</CardTitle>
                            <CardDescription>
                                Entre com suas credenciais de contador para gerenciar campanhas
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
                                        data-testid="contador-login-email"
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
                                            data-testid="contador-login-password"
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
                                    className="w-full h-12 font-semibold gap-2 bg-emerald-600 hover:bg-emerald-700"
                                    disabled={loading}
                                    data-testid="contador-login-submit"
                                >
                                    {loading ? 'Entrando...' : 'Acessar Portal'}
                                    {!loading && <ArrowRight className="h-4 w-4" />}
                                </Button>
                            </form>

                            <div className="mt-6 p-4 rounded-lg bg-muted/50 border border-dashed">
                                <p className="text-xs text-muted-foreground text-center">
                                    <strong>Contadores Ativa:</strong> Use o email corporativo para acessar.
                                    <br />
                                    <strong>Admin:</strong> diretoria@ativacontabilidade.cnt.br
                                </p>
                            </div>
                        </CardContent>
                    </Card>

                    <div className="mt-6 text-center">
                        <a 
                            href="/login" 
                            className="text-sm text-muted-foreground hover:text-primary transition-colors"
                        >
                            Voltar ao login de candidato
                        </a>
                    </div>
                </div>
            </div>

            {/* Right side - Branding */}
            <div className="hidden lg:flex flex-1 relative overflow-hidden bg-emerald-900">
                <div className="absolute inset-0 bg-gradient-to-br from-emerald-800/80 to-emerald-950" />
                <div className="absolute inset-0 flex items-center justify-center p-12">
                    <div className="text-center text-white">
                        <Calculator className="h-20 w-20 mx-auto mb-6 opacity-80" />
                        <h2 className="font-heading text-4xl font-bold mb-4">
                            Portal do<br />Contador
                        </h2>
                        <p className="text-lg text-emerald-100 max-w-md">
                            Gerencie as prestações de contas eleitorais de todos os seus clientes em um só lugar
                        </p>
                        <div className="mt-8 grid grid-cols-2 gap-4 text-left max-w-sm mx-auto">
                            <div className="p-3 rounded-lg bg-white/10 backdrop-blur">
                                <p className="font-semibold">Visão Consolidada</p>
                                <p className="text-sm text-emerald-200">Todas as campanhas</p>
                            </div>
                            <div className="p-3 rounded-lg bg-white/10 backdrop-blur">
                                <p className="font-semibold">Limites TSE</p>
                                <p className="text-sm text-emerald-200">Alertas automáticos</p>
                            </div>
                            <div className="p-3 rounded-lg bg-white/10 backdrop-blur">
                                <p className="font-semibold">SPCE Export</p>
                                <p className="text-sm text-emerald-200">Relatórios oficiais</p>
                            </div>
                            <div className="p-3 rounded-lg bg-white/10 backdrop-blur">
                                <p className="font-semibold">Equipe</p>
                                <p className="text-sm text-emerald-200">Gerencie contadores</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
