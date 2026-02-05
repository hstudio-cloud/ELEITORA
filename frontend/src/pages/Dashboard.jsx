import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { useAuth } from '../contexts/AuthContext';
import { formatCurrency, categoryLabels } from '../lib/utils';
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
    AlertTriangle
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

export default function Dashboard() {
    const [stats, setStats] = useState(null);
    const [campaign, setCampaign] = useState(null);
    const [loading, setLoading] = useState(true);
    const { user } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            const [statsRes, campaignRes] = await Promise.all([
                axios.get(`${API}/dashboard/stats`),
                axios.get(`${API}/campaigns/my`)
            ]);
            setStats(statsRes.data);
            setCampaign(campaignRes.data);
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
        </Layout>
    );
}
