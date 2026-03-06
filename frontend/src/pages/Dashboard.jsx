import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle
} from '../components/ui/dialog';
import { useAuth } from '../contexts/AuthContext';
import { formatCurrency, categoryLabels } from '../lib/utils';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import {
    TrendingUp,
    TrendingDown,
    Wallet,
    FileText,
    CreditCard,
    ArrowUpRight,
    ArrowDownRight,
    Plus,
    AlertCircle,
    Bell,
    Clock,
    AlertTriangle,
    Sparkles,
    Volume2,
    VolumeX,
    ChevronLeft,
    ChevronRight
} from 'lucide-react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell
} from 'recharts';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const COLORS = ['hsl(217, 91%, 60%)', 'hsl(160, 84%, 39%)', 'hsl(38, 92%, 50%)', 'hsl(0, 84%, 60%)', 'hsl(280, 65%, 60%)'];

const TOUR_STEPS = [

        {
            title: 'Bem-vindo ao Eleitora 360',
            description: 'Este tour rápido mostra como organizar sua campanha e evitar erros na prestação de contas.',
            route: '/dashboard',
            actionLabel: 'Ficar no Dashboard'
        },
        {
            title: '1) Comece por Configurações',
            description: 'Cadastre dados da campanha, CNPJ, contas bancárias e informações obrigatórias do TSE/SPCE.',
            route: '/configuracoes',
            actionLabel: 'Abrir Configurações'
        },
        {
            title: '2) Lance as Receitas',
            description: 'Registre doações e entradas com CPF/CNPJ do doador e comprovantes.',
            route: '/receitas',
            actionLabel: 'Abrir Receitas'
        },
        {
            title: '3) Lance as Despesas',
            description: 'Cadastre gastos com categoria, fornecedor e documentos para manter conformidade.',
            route: '/despesas',
            actionLabel: 'Abrir Despesas'
        },
        {
            title: '4) Gere Contratos',
            description: 'Ao criar contrato, o sistema já pode gerar as despesas vinculadas automaticamente.',
            route: '/contratos',
            actionLabel: 'Abrir Contratos'
        },
        {
            title: '5) Agende Pagamentos PIX',
            description: 'Use a área de Pagamentos para agendar e acompanhar execução das despesas da campanha.',
            route: '/pagamentos',
            actionLabel: 'Abrir Pagamentos'
        },
        {
            title: '6) Faça o Pré-check SPCE',
            description: 'Antes de exportar, rode o pré-check SPCE para identificar pendências e evitar rejeição.',
            route: '/relatorios',
            actionLabel: 'Abrir Relatórios'
        },
        {
            title: '7) Use o Assistente IA',
            description: 'A Flora pode te orientar sobre próximos passos, conformidade e dúvidas operacionais.',
            route: '/assistente',
            actionLabel: 'Abrir Assistente'
        }
    ];


export default function Dashboard() {
    const [stats, setStats] = useState(null);
    const [campaign, setCampaign] = useState(null);
    const [loading, setLoading] = useState(true);
    const [alerts, setAlerts] = useState({ alerts: [], total: 0, overdue_count: 0, due_today: 0 });
    const [tseStatus, setTseStatus] = useState(null);
    const [showTour, setShowTour] = useState(false);
    const [tourStep, setTourStep] = useState(0);
    const [tourSpeakEnabled, setTourSpeakEnabled] = useState(true);
    const tourAudioRef = useRef(null);
    const { user } = useAuth();
    const navigate = useNavigate();

    const tourStorageKey = user?.id ? `eleitora_tour_done_${user.id}` : null;

    useEffect(() => {
        fetchData();
    }, []);

    useEffect(() => {
        if (!user || loading || !tourStorageKey) return;
        const alreadyDone = localStorage.getItem(tourStorageKey) === '1';
        if (!alreadyDone) {
            setShowTour(true);
            setTourStep(0);
        }
    }, [user, loading, tourStorageKey]);

    const speakTourWithFlora = useCallback(async (text) => {
        if (!tourSpeakEnabled || !text) return;
        try {
            const response = await axios.post(`${API}/voice/speak?text=${encodeURIComponent(text.substring(0, 500))}`);
            if (response.data?.audio) {
                if (tourAudioRef.current) {
                    tourAudioRef.current.pause();
                    tourAudioRef.current.currentTime = 0;
                }
                const audio = new Audio(`data:audio/mp3;base64,${response.data.audio}`);
                tourAudioRef.current = audio;
                audio.play().catch(() => {});
                return;
            }
        } catch (error) {
            console.error('Erro no voice/speak do tour:', error);
        }

        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(text);
            const voices = window.speechSynthesis.getVoices();
            const preferredVoice =
                voices.find(v => /pt-BR/i.test(v.lang) && /female|mulher|google|microsoft/i.test(v.name)) ||
                voices.find(v => /pt-BR/i.test(v.lang)) ||
                voices[0];
            if (preferredVoice) utterance.voice = preferredVoice;
            utterance.lang = 'pt-BR';
            utterance.rate = 1;
            utterance.pitch = 1.1;
            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(utterance);
        }
    }, [tourSpeakEnabled]);

    useEffect(() => {
        if (!showTour || !tourSpeakEnabled) return;
        const step = TOUR_STEPS[tourStep];
        if (!step) return;
        speakTourWithFlora(`${step.title}. ${step.description}`);

        return () => {
            if (tourAudioRef.current) {
                tourAudioRef.current.pause();
                tourAudioRef.current.currentTime = 0;
            }
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
            }
        };
    }, [showTour, tourSpeakEnabled, tourStep, speakTourWithFlora]);

    const fetchData = async () => {
        try {
            const [statsRes, campaignRes, alertsRes, tseRes] = await Promise.all([
                axios.get(`${API}/dashboard/stats`),
                axios.get(`${API}/campaigns/my`),
                axios.get(`${API}/payments/alerts?days_ahead=7`).catch(() => ({ data: { alerts: [], total: 0 } })),
                axios.get(`${API}/tse/campaign-status`).catch(() => ({ data: null }))
            ]);
            setStats(statsRes.data);
            setCampaign(campaignRes.data);
            setAlerts(alertsRes.data);
            setTseStatus(tseRes.data);
        } catch (error) {
            toast.error('Erro ao carregar dados');
        } finally {
            setLoading(false);
        }
    };

    const formatPieData = (data) => {
        return Object.entries(data || {}).map(([key, value]) => ({
            name: categoryLabels[key] || key,
            value
        }));
    };

    const finishTour = () => {
        if (tourStorageKey) {
            localStorage.setItem(tourStorageKey, '1');
        }
        setShowTour(false);
        setTourStep(0);
        if (tourAudioRef.current) {
            tourAudioRef.current.pause();
            tourAudioRef.current.currentTime = 0;
        }
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
        toast.success('Tour concluído. Você pode reabrir quando quiser.');
    };

    const skipTour = () => {
        finishTour();
    };

    const openCurrentTourStep = () => {
        const step = TOUR_STEPS[tourStep];
        if (!step?.route) return;
        if (tourStorageKey) {
            localStorage.setItem(tourStorageKey, '1');
        }
        setShowTour(false);
        navigate(step.route);
    };

    if (loading) {
        return (
            <Layout>
                <div className="flex items-center justify-center h-96">
                    <div className="animate-pulse text-muted-foreground">Carregando...</div>
                </div>
            </Layout>
        );
    }

    if (!campaign) {
        return (
            <Layout>
                <div className="max-w-2xl mx-auto mt-20 text-center animate-fade-in-up" data-testid="no-campaign-warning">
                    <div className="w-20 h-20 rounded-full bg-accent/20 flex items-center justify-center mx-auto mb-6">
                        <AlertCircle className="h-10 w-10 text-accent" />
                    </div>
                    <h2 className="font-heading text-3xl font-bold mb-4">Configure sua Campanha</h2>
                    <p className="text-muted-foreground mb-8">
                        Para começar a usar o sistema, você precisa configurar os dados da sua campanha eleitoral.
                    </p>
                    <Button
                        size="lg"
                        className="gap-2"
                        onClick={() => navigate('/configuracoes')}
                        data-testid="configure-campaign-btn"
                    >
                        <Plus className="h-5 w-5" />
                        Configurar Campanha
                    </Button>
                </div>
            </Layout>
        );
    }

    return (
        <Layout>
            <div className="space-y-8" data-testid="dashboard-page">
                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 animate-fade-in">
                    <div>
                        <h1 className="font-heading text-3xl font-bold">Dashboard</h1>
                        <p className="text-muted-foreground">
                            Campanha de {campaign.candidate_name} - {campaign.party}
                        </p>
                    </div>
                    <div className="flex gap-3">
                        <Button
                            variant="secondary"
                            onClick={() => setShowTour(true)}
                            className="gap-2"
                            data-testid="open-guided-tour-btn"
                        >
                            <Sparkles className="h-4 w-4" />
                            Tour da Flora
                        </Button>
                        <Button
                            variant="outline"
                            onClick={() => navigate('/receitas')}
                            className="gap-2"
                            data-testid="add-revenue-btn"
                        >
                            <TrendingUp className="h-4 w-4 text-secondary" />
                            Nova Receita
                        </Button>
                        <Button
                            variant="outline"
                            onClick={() => navigate('/despesas')}
                            className="gap-2"
                            data-testid="add-expense-btn"
                        >
                            <TrendingDown className="h-4 w-4 text-destructive" />
                            Nova Despesa
                        </Button>
                    </div>
                </div>

                {/* KPI Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <Card className="animate-fade-in-up stagger-1" data-testid="total-revenue-card">
                        <CardContent className="p-6">
                            <div className="flex items-start justify-between">
                                <div>
                                    <p className="text-sm text-muted-foreground mb-1">Total Receitas</p>
                                    <p className="font-heading text-2xl font-bold text-secondary">
                                        {formatCurrency(stats?.total_revenues)}
                                    </p>
                                </div>
                                <div className="w-12 h-12 rounded-lg bg-secondary/20 flex items-center justify-center">
                                    <ArrowUpRight className="h-6 w-6 text-secondary" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="animate-fade-in-up stagger-2" data-testid="total-expense-card">
                        <CardContent className="p-6">
                            <div className="flex items-start justify-between">
                                <div>
                                    <p className="text-sm text-muted-foreground mb-1">Total Despesas</p>
                                    <p className="font-heading text-2xl font-bold text-destructive">
                                        {formatCurrency(stats?.total_expenses)}
                                    </p>
                                </div>
                                <div className="w-12 h-12 rounded-lg bg-destructive/20 flex items-center justify-center">
                                    <ArrowDownRight className="h-6 w-6 text-destructive" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="animate-fade-in-up stagger-3" data-testid="balance-card">
                        <CardContent className="p-6">
                            <div className="flex items-start justify-between">
                                <div>
                                    <p className="text-sm text-muted-foreground mb-1">Saldo</p>
                                    <p className={`font-heading text-2xl font-bold ${stats?.balance >= 0 ? 'text-secondary' : 'text-destructive'}`}>
                                        {formatCurrency(stats?.balance)}
                                    </p>
                                </div>
                                <div className="w-12 h-12 rounded-lg bg-primary/20 flex items-center justify-center">
                                    <Wallet className="h-6 w-6 text-primary" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="animate-fade-in-up stagger-4" data-testid="pending-card">
                        <CardContent className="p-6">
                            <div className="flex items-start justify-between">
                                <div>
                                    <p className="text-sm text-muted-foreground mb-1">Pendências</p>
                                    <div className="flex items-baseline gap-4">
                                        <div>
                                            <span className="font-heading text-2xl font-bold text-accent">
                                                {stats?.pending_payments}
                                            </span>
                                            <span className="text-sm text-muted-foreground ml-1">pgtos</span>
                                        </div>
                                        <div>
                                            <span className="font-heading text-2xl font-bold">
                                                {stats?.active_contracts}
                                            </span>
                                            <span className="text-sm text-muted-foreground ml-1">contratos</span>
                                        </div>
                                    </div>
                                </div>
                                <div className="w-12 h-12 rounded-lg bg-accent/20 flex items-center justify-center">
                                    <FileText className="h-6 w-6 text-accent" />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* TSE Spending Limit Alert */}
                {tseStatus && (
                    <Card className={`animate-fade-in-up ${
                        tseStatus.status === 'excedido' ? 'border-destructive bg-destructive/5' :
                        tseStatus.status === 'critico' ? 'border-accent bg-accent/5' :
                        tseStatus.status === 'atencao' ? 'border-yellow-500 bg-yellow-500/5' :
                        'border-secondary bg-secondary/5'
                    }`} data-testid="tse-limit-card">
                        <CardContent className="p-6">
                            <div className="flex items-start justify-between gap-4">
                                <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-2">
                                        <AlertTriangle className={`h-5 w-5 ${
                                            tseStatus.status === 'excedido' ? 'text-destructive' :
                                            tseStatus.status === 'critico' ? 'text-accent' :
                                            tseStatus.status === 'atencao' ? 'text-yellow-500' :
                                            'text-secondary'
                                        }`} />
                                        <h3 className="font-heading text-lg font-semibold">Limite de Gastos TSE</h3>
                                        <Badge variant={
                                            tseStatus.status === 'excedido' ? 'destructive' :
                                            tseStatus.status === 'critico' ? 'default' :
                                            tseStatus.status === 'atencao' ? 'outline' :
                                            'secondary'
                                        }>
                                            {tseStatus.status === 'excedido' ? 'EXCEDIDO' :
                                             tseStatus.status === 'critico' ? 'CRÍTICO' :
                                             tseStatus.status === 'atencao' ? 'ATENÇÃO' : 'OK'}
                                        </Badge>
                                    </div>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                                        <div>
                                            <p className="text-xs text-muted-foreground">Limite TSE</p>
                                            <p className="font-semibold">{tseStatus.spending?.limite_formatado}</p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-muted-foreground">Total Gasto</p>
                                            <p className="font-semibold text-destructive">{tseStatus.spending?.total_gasto_formatado}</p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-muted-foreground">Disponível</p>
                                            <p className={`font-semibold ${tseStatus.spending?.saldo_disponivel >= 0 ? 'text-secondary' : 'text-destructive'}`}>
                                                {tseStatus.spending?.saldo_formatado}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-xs text-muted-foreground">Utilizado</p>
                                            <div className="flex items-center gap-2">
                                                <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                                                    <div 
                                                        className={`h-full transition-all ${
                                                            tseStatus.spending?.percentual_utilizado >= 100 ? 'bg-destructive' :
                                                            tseStatus.spending?.percentual_utilizado >= 90 ? 'bg-accent' :
                                                            tseStatus.spending?.percentual_utilizado >= 75 ? 'bg-yellow-500' :
                                                            'bg-secondary'
                                                        }`}
                                                        style={{ width: `${Math.min(tseStatus.spending?.percentual_utilizado || 0, 100)}%` }}
                                                    />
                                                </div>
                                                <span className="text-sm font-medium">{tseStatus.spending?.percentual_utilizado}%</span>
                                            </div>
                                        </div>
                                    </div>
                                    {tseStatus.alerts?.length > 0 && (
                                        <div className="mt-4 p-3 rounded-lg bg-background/50 border">
                                            <p className="text-sm">{tseStatus.alerts[0].message}</p>
                                            <p className="text-xs text-muted-foreground mt-1">{tseStatus.alerts[0].detail}</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Charts */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Monthly Flow Chart */}
                    <Card className="animate-fade-in-up stagger-5" data-testid="monthly-chart">
                        <CardHeader>
                            <CardTitle className="font-heading">Fluxo Mensal</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="h-80">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={stats?.monthly_flow || []}>
                                        <XAxis
                                            dataKey="month"
                                            stroke="hsl(var(--muted-foreground))"
                                            fontSize={12}
                                            tickLine={false}
                                            axisLine={false}
                                        />
                                        <YAxis
                                            stroke="hsl(var(--muted-foreground))"
                                            fontSize={12}
                                            tickLine={false}
                                            axisLine={false}
                                            tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
                                        />
                                        <Tooltip
                                            contentStyle={{
                                                backgroundColor: 'hsl(var(--card))',
                                                border: '1px solid hsl(var(--border))',
                                                borderRadius: '8px'
                                            }}
                                            formatter={(value) => formatCurrency(value)}
                                        />
                                        <Bar dataKey="receitas" fill="hsl(160, 84%, 39%)" radius={[4, 4, 0, 0]} />
                                        <Bar dataKey="despesas" fill="hsl(0, 84%, 60%)" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Pie Charts */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                        <Card className="animate-fade-in-up stagger-6" data-testid="revenue-pie-chart">
                            <CardHeader className="pb-2">
                                <CardTitle className="font-heading text-lg">Receitas por Categoria</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="h-48">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie
                                                data={formatPieData(stats?.revenues_by_category)}
                                                cx="50%"
                                                cy="50%"
                                                innerRadius={40}
                                                outerRadius={70}
                                                paddingAngle={2}
                                                dataKey="value"
                                            >
                                                {formatPieData(stats?.revenues_by_category).map((entry, index) => (
                                                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                                ))}
                                            </Pie>
                                            <Tooltip
                                                contentStyle={{
                                                    backgroundColor: 'hsl(var(--card))',
                                                    border: '1px solid hsl(var(--border))',
                                                    borderRadius: '8px'
                                                }}
                                                formatter={(value) => formatCurrency(value)}
                                            />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="animate-fade-in-up stagger-6" data-testid="expense-pie-chart">
                            <CardHeader className="pb-2">
                                <CardTitle className="font-heading text-lg">Despesas por Categoria</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="h-48">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie
                                                data={formatPieData(stats?.expenses_by_category)}
                                                cx="50%"
                                                cy="50%"
                                                innerRadius={40}
                                                outerRadius={70}
                                                paddingAngle={2}
                                                dataKey="value"
                                            >
                                                {formatPieData(stats?.expenses_by_category).map((entry, index) => (
                                                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                                ))}
                                            </Pie>
                                            <Tooltip
                                                contentStyle={{
                                                    backgroundColor: 'hsl(var(--card))',
                                                    border: '1px solid hsl(var(--border))',
                                                    borderRadius: '8px'
                                                }}
                                                formatter={(value) => formatCurrency(value)}
                                            />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>

                {/* Payment Alerts */}
                {alerts.total > 0 && (
                    <Card className="animate-fade-in-up border-accent/50" data-testid="payment-alerts-card">
                        <CardHeader className="pb-3">
                            <div className="flex items-center justify-between">
                                <CardTitle className="font-heading flex items-center gap-2">
                                    <Bell className="h-5 w-5 text-accent" />
                                    Alertas de Pagamento
                                    {alerts.overdue_count > 0 && (
                                        <Badge variant="destructive" className="ml-2">
                                            {alerts.overdue_count} atrasado{alerts.overdue_count > 1 ? 's' : ''}
                                        </Badge>
                                    )}
                                </CardTitle>
                                <Button 
                                    variant="ghost" 
                                    size="sm" 
                                    onClick={() => navigate('/pagamentos')}
                                    className="text-accent"
                                >
                                    Ver todos
                                </Button>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-3">
                                {alerts.alerts.slice(0, 5).map((alert, index) => (
                                    <div 
                                        key={index}
                                        className={`flex items-center justify-between p-3 rounded-lg ${
                                            alert.is_overdue 
                                                ? 'bg-destructive/10 border border-destructive/30' 
                                                : alert.days_until_due <= 3 
                                                    ? 'bg-accent/10 border border-accent/30' 
                                                    : 'bg-muted/50'
                                        }`}
                                        data-testid={`alert-${index}`}
                                    >
                                        <div className="flex items-center gap-3">
                                            {alert.is_overdue ? (
                                                <AlertTriangle className="h-5 w-5 text-destructive" />
                                            ) : alert.days_until_due <= 3 ? (
                                                <AlertCircle className="h-5 w-5 text-accent" />
                                            ) : (
                                                <Clock className="h-5 w-5 text-muted-foreground" />
                                            )}
                                            <div>
                                                <p className="font-medium text-sm">{alert.description}</p>
                                                <p className="text-xs text-muted-foreground">
                                                    {alert.is_overdue 
                                                        ? `Vencido há ${Math.abs(alert.days_until_due)} dia${Math.abs(alert.days_until_due) > 1 ? 's' : ''}`
                                                        : alert.days_until_due === 0 
                                                            ? 'Vence hoje!'
                                                            : `Vence em ${alert.days_until_due} dia${alert.days_until_due > 1 ? 's' : ''}`
                                                    }
                                                </p>
                                            </div>
                                        </div>
                                        <span className={`font-mono font-bold ${alert.is_overdue ? 'text-destructive' : 'text-accent'}`}>
                                            {formatCurrency(alert.amount)}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Quick Actions */}
                <Card className="animate-fade-in-up" data-testid="quick-actions">
                    <CardHeader>
                        <CardTitle className="font-heading">Ações Rápidas</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <Button
                                variant="outline"
                                className="h-auto py-6 flex-col gap-2"
                                onClick={() => navigate('/receitas')}
                                data-testid="quick-receitas-btn"
                            >
                                <TrendingUp className="h-6 w-6 text-secondary" />
                                <span>Receitas</span>
                            </Button>
                            <Button
                                variant="outline"
                                className="h-auto py-6 flex-col gap-2"
                                onClick={() => navigate('/despesas')}
                                data-testid="quick-despesas-btn"
                            >
                                <TrendingDown className="h-6 w-6 text-destructive" />
                                <span>Despesas</span>
                            </Button>
                            <Button
                                variant="outline"
                                className="h-auto py-6 flex-col gap-2"
                                onClick={() => navigate('/contratos')}
                                data-testid="quick-contratos-btn"
                            >
                                <FileText className="h-6 w-6 text-primary" />
                                <span>Contratos</span>
                            </Button>
                            <Button
                                variant="outline"
                                className="h-auto py-6 flex-col gap-2"
                                onClick={() => navigate('/relatorios')}
                                data-testid="quick-relatorios-btn"
                            >
                                <CreditCard className="h-6 w-6 text-accent" />
                                <span>Relatórios</span>
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>

            <Dialog open={showTour} onOpenChange={setShowTour}>
                <DialogContent className="sm:max-w-xl" data-testid="eleitora-onboarding-tour">
                    <DialogHeader>
                        <DialogTitle className="flex items-center justify-between gap-3">
                            <span className="flex items-center gap-2">
                                <Sparkles className="h-5 w-5 text-primary" />
                                {TOUR_STEPS[tourStep]?.title}
                            </span>
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => setTourSpeakEnabled((prev) => !prev)}
                                aria-label="Alternar voz do tour"
                            >
                                {tourSpeakEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
                            </Button>
                        </DialogTitle>
                        <DialogDescription>
                            {TOUR_STEPS[tourStep]?.description}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">
                            Etapa {tourStep + 1} de {TOUR_STEPS.length}
                        </span>
                        <Badge variant="outline">Onboarding IA</Badge>
                    </div>

                    <DialogFooter className="gap-2">
                        <Button variant="ghost" onClick={skipTour}>
                            Pular tour
                        </Button>
                        <Button
                            variant="outline"
                            onClick={() => setTourStep((prev) => Math.max(0, prev - 1))}
                            disabled={tourStep === 0}
                            className="gap-2"
                        >
                            <ChevronLeft className="h-4 w-4" />
                            Anterior
                        </Button>
                        <Button variant="outline" onClick={openCurrentTourStep}>
                            {TOUR_STEPS[tourStep]?.actionLabel}
                        </Button>
                        {tourStep < TOUR_STEPS.length - 1 ? (
                            <Button
                                onClick={() => setTourStep((prev) => Math.min(TOUR_STEPS.length - 1, prev + 1))}
                                className="gap-2"
                            >
                                Próximo
                                <ChevronRight className="h-4 w-4" />
                            </Button>
                        ) : (
                            <Button onClick={finishTour}>Concluir tour</Button>
                        )}
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </Layout>
    );
}
