import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { Vote, Eye, EyeOff, ArrowRight } from 'lucide-react';

export default function Register() {
    const [formData, setFormData] = useState({
        name: '',
        email: '',
        password: '',
        confirmPassword: '',
        role: 'candidato',
        cpf: '',
        phone: ''
    });
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const { register } = useAuth();
    const navigate = useNavigate();

    const handleChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (formData.password !== formData.confirmPassword) {
            toast.error('As senhas não coincidem');
            return;
        }

        if (formData.password.length < 6) {
            toast.error('A senha deve ter pelo menos 6 caracteres');
            return;
        }

        setLoading(true);

        try {
            const { confirmPassword, ...userData } = formData;
            await register(userData);
            toast.success('Conta criada com sucesso!');
            navigate('/dashboard');
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao criar conta');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex" data-testid="register-page">
            {/* Left side - Image */}
            <div className="hidden lg:flex flex-1 relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-bl from-secondary/20 to-primary/20" />
                <img
                    src="https://images.pexels.com/photos/1367274/pexels-photo-1367274.jpeg"
                    alt="Professional team"
                    className="w-full h-full object-cover opacity-50"
                />
                <div className="absolute inset-0 flex items-center justify-center p-12">
                    <div className="text-center">
                        <h2 className="font-heading text-4xl font-bold mb-4">
                            Sua campanha<br />em boas mãos
                        </h2>
                        <p className="text-lg text-muted-foreground max-w-md">
                            Plataforma completa para gestão eleitoral e contábil
                        </p>
                    </div>
                </div>
            </div>

            {/* Right side - Form */}
            <div className="flex-1 flex items-center justify-center p-8 overflow-y-auto">
                <div className="w-full max-w-md animate-fade-in-up">
                    <div className="flex items-center gap-3 mb-8">
                        <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center">
                            <Vote className="h-6 w-6 text-primary" />
                        </div>
                        <div>
                            <h1 className="font-heading text-2xl font-bold">Eleitora 360</h1>
                            <p className="text-sm text-muted-foreground">Gestão Eleitoral Inteligente</p>
                        </div>
                    </div>

                    <Card className="border-border bg-card">
                        <CardHeader className="space-y-1">
                            <CardTitle className="font-heading text-2xl">Criar Conta</CardTitle>
                            <CardDescription>
                                Preencha os dados para começar a usar a plataforma
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={handleSubmit} className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="name">Nome Completo</Label>
                                    <Input
                                        id="name"
                                        placeholder="Seu nome"
                                        value={formData.name}
                                        onChange={(e) => handleChange('name', e.target.value)}
                                        required
                                        className="h-12"
                                        data-testid="register-name-input"
                                    />
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="email">Email</Label>
                                    <Input
                                        id="email"
                                        type="email"
                                        placeholder="seu@email.com"
                                        value={formData.email}
                                        onChange={(e) => handleChange('email', e.target.value)}
                                        required
                                        className="h-12"
                                        data-testid="register-email-input"
                                    />
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="role">Tipo de Usuário</Label>
                                    <Select
                                        value={formData.role}
                                        onValueChange={(value) => handleChange('role', value)}
                                    >
                                        <SelectTrigger className="h-12" data-testid="register-role-select">
                                            <SelectValue placeholder="Selecione o tipo" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="candidato">Candidato</SelectItem>
                                            <SelectItem value="contador">Contador</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label htmlFor="cpf">CPF (opcional)</Label>
                                        <Input
                                            id="cpf"
                                            placeholder="000.000.000-00"
                                            value={formData.cpf}
                                            onChange={(e) => handleChange('cpf', e.target.value)}
                                            className="h-12"
                                            data-testid="register-cpf-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="phone">Telefone (opcional)</Label>
                                        <Input
                                            id="phone"
                                            placeholder="(00) 00000-0000"
                                            value={formData.phone}
                                            onChange={(e) => handleChange('phone', e.target.value)}
                                            className="h-12"
                                            data-testid="register-phone-input"
                                        />
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="password">Senha</Label>
                                    <div className="relative">
                                        <Input
                                            id="password"
                                            type={showPassword ? 'text' : 'password'}
                                            placeholder="••••••••"
                                            value={formData.password}
                                            onChange={(e) => handleChange('password', e.target.value)}
                                            required
                                            className="h-12 pr-10"
                                            data-testid="register-password-input"
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

                                <div className="space-y-2">
                                    <Label htmlFor="confirmPassword">Confirmar Senha</Label>
                                    <Input
                                        id="confirmPassword"
                                        type={showPassword ? 'text' : 'password'}
                                        placeholder="••••••••"
                                        value={formData.confirmPassword}
                                        onChange={(e) => handleChange('confirmPassword', e.target.value)}
                                        required
                                        className="h-12"
                                        data-testid="register-confirm-password-input"
                                    />
                                </div>

                                <Button
                                    type="submit"
                                    className="w-full h-12 font-semibold gap-2"
                                    disabled={loading}
                                    data-testid="register-submit-btn"
                                >
                                    {loading ? 'Criando conta...' : 'Criar Conta'}
                                    {!loading && <ArrowRight className="h-4 w-4" />}
                                </Button>
                            </form>

                            <div className="mt-6 text-center">
                                <p className="text-sm text-muted-foreground">
                                    Já tem uma conta?{' '}
                                    <Link
                                        to="/login"
                                        className="text-primary hover:underline font-medium"
                                        data-testid="login-link"
                                    >
                                        Entrar
                                    </Link>
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
