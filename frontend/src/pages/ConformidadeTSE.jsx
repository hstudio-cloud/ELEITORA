import { useState, useEffect } from 'react';
import axios from 'axios';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { toast } from 'sonner';
import { 
    CheckCircle2, AlertTriangle, XCircle, Info, FileText, 
    Users, DollarSign, FileSignature, Paperclip, ChevronRight,
    RefreshCw, Download, ArrowRight, AlertCircle
} from 'lucide-react';
import { Link } from 'react-router-dom';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const statusConfig = {
    pronto: { 
        color: 'bg-emerald-500', 
        textColor: 'text-emerald-500',
        bgLight: 'bg-emerald-500/10',
        icon: CheckCircle2,
        label: 'Pronto para Envio'
    },
    quase_pronto: { 
        color: 'bg-blue-500', 
        textColor: 'text-blue-500',
        bgLight: 'bg-blue-500/10',
        icon: Info,
        label: 'Quase Pronto'
    },
    em_andamento: { 
        color: 'bg-yellow-500', 
        textColor: 'text-yellow-500',
        bgLight: 'bg-yellow-500/10',
        icon: AlertTriangle,
        label: 'Em Andamento'
    },
    incompleto: { 
        color: 'bg-red-500', 
        textColor: 'text-red-500',
        bgLight: 'bg-red-500/10',
        icon: XCircle,
        label: 'Incompleto'
    }
};

const categoryIcons = {
    'Dados da Campanha': Users,
    'Receitas': DollarSign,
    'Despesas': DollarSign,
    'Contratos': FileSignature,
    'Documentos ComprobatÃ³rios': Paperclip
};

const categoryLinks = {
    'Dados da Campanha': '/configuracoes',
    'Receitas': '/receitas',
    'Despesas': '/despesas',
    'Contratos': '/contratos',
    'Documentos ComprobatÃ³rios': '/despesas'
};

export default function ConformidadeTSE() {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            const response = await axios.get(`${API}/dashboard/conformidade-tse`);
            setData(response.data);
        } catch (error) {
            toast.error('Erro ao carregar dados de conformidade');
        } finally {
            setLoading(false);
        }
    };

    const formatCurrency = (value) => {
        return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value || 0);
    };

    const getProgressColor = (perc) => {
        if (perc >= 90) return 'bg-emerald-500';
        if (perc >= 70) return 'bg-blue-500';
        if (perc >= 50) return 'bg-yellow-500';
        return 'bg-red-500';
    };

    if (loading) {
        return (
            <Layout>
                <div className="flex items-center justify-center h-96">
                    <div className="animate-pulse text-muted-foreground">Analisando conformidade...</div>
                </div>
            </Layout>
        );
    }

    const statusInfo = statusConfig[data?.status] || statusConfig.incompleto;
    const StatusIcon = statusInfo.icon;

    return (
        <Layout>
            <div className="space-y-6" data-testid="conformidade-page">
                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div>
                        <h1 className="font-heading text-3xl font-bold">Conformidade TSE</h1>
                        <p className="text-muted-foreground">VerificaÃ§Ã£o de completude para prestaÃ§Ã£o de contas</p>
                    </div>
                    <div className="flex gap-3">
                        <Button variant="outline" className="gap-2" onClick={fetchData}>
                            <RefreshCw className="h-4 w-4" />
                            Atualizar
                        </Button>
                        <Link to="/relatorios">
                            <Button className="gap-2" disabled={data?.completude_geral < 70}>
                                <Download className="h-4 w-4" />
                                Exportar SPCE
                            </Button>
                        </Link>
                    </div>
                </div>

                {/* Main Status Card */}
                <Card className={`${statusInfo.bgLight} border-2 ${statusInfo.textColor.replace('text-', 'border-')}/30`}>
                    <CardContent className="p-8">
                        <div className="flex flex-col md:flex-row md:items-center gap-8">
                            {/* Progress Circle */}
                            <div className="relative">
                                <svg className="w-40 h-40 transform -rotate-90">
                                    <circle
                                        cx="80"
                                        cy="80"
                                        r="70"
                                        stroke="currentColor"
                                        strokeWidth="12"
                                        fill="transparent"
                                        className="text-muted/20"
                                    />
                                    <circle
                                        cx="80"
                                        cy="80"
                                        r="70"
                                        stroke="currentColor"
                                        strokeWidth="12"
                                        fill="transparent"
                                        strokeDasharray={`${(data?.completude_geral || 0) * 4.4} 440`}
                                        className={statusInfo.textColor}
                                        strokeLinecap="round"
                                    />
                                </svg>
                                <div className="absolute inset-0 flex flex-col items-center justify-center">
                                    <span className={`text-4xl font-bold ${statusInfo.textColor}`}>
                                        {data?.completude_geral || 0}%
                                    </span>
                                    <span className="text-sm text-muted-foreground">Completo</span>
                                </div>
                            </div>

                            {/* Status Info */}
                            <div className="flex-1">
                                <div className="flex items-center gap-3 mb-2">
                                    <StatusIcon className={`h-8 w-8 ${statusInfo.textColor}`} />
                                    <Badge className={`${statusInfo.color} text-white text-lg px-4 py-1`}>
                                        {statusInfo.label}
                                    </Badge>
                                </div>
                                <p className="text-lg text-muted-foreground mb-4">{data?.message}</p>
                                
                                {/* Quick Stats */}
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                    <div className="text-center p-3 rounded-lg bg-background/50">
                                        <p className="text-2xl font-bold">{data?.resumo?.total_receitas || 0}</p>
                                        <p className="text-xs text-muted-foreground">Receitas</p>
                                    </div>
                                    <div className="text-center p-3 rounded-lg bg-background/50">
                                        <p className="text-2xl font-bold">{data?.resumo?.total_despesas || 0}</p>
                                        <p className="text-xs text-muted-foreground">Despesas</p>
                                    </div>
                                    <div className="text-center p-3 rounded-lg bg-background/50">
                                        <p className="text-2xl font-bold">{data?.resumo?.total_contratos || 0}</p>
                                        <p className="text-xs text-muted-foreground">Contratos</p>
                                    </div>
                                    <div className="text-center p-3 rounded-lg bg-background/50">
                                        <p className="text-lg font-bold text-emerald-500">
                                            {formatCurrency(data?.resumo?.valor_receitas)}
                                        </p>
                                        <p className="text-xs text-muted-foreground">Total Receitas</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                {/* Alerts */}
                {data?.alertas?.length > 0 && (
                    <div className="space-y-3">
                        <h2 className="font-heading text-lg font-semibold flex items-center gap-2">
                            <AlertCircle className="h-5 w-5 text-yellow-500" />
                            AÃ§Ãµes Pendentes
                        </h2>
                        <div className="grid gap-3">
                            {data.alertas.map((alerta, index) => (
                                <Card 
                                    key={index} 
                                    className={`border-l-4 ${
                                        alerta.tipo === 'erro' ? 'border-l-red-500 bg-red-500/5' :
                                        alerta.tipo === 'aviso' ? 'border-l-yellow-500 bg-yellow-500/5' :
                                        'border-l-blue-500 bg-blue-500/5'
                                    }`}
                                >
                                    <CardContent className="p-4">
                                        <div className="flex items-start justify-between gap-4">
                                            <div className="flex items-start gap-3">
                                                {alerta.tipo === 'erro' ? (
                                                    <XCircle className="h-5 w-5 text-red-500 mt-0.5" />
                                                ) : alerta.tipo === 'aviso' ? (
                                                    <AlertTriangle className="h-5 w-5 text-yellow-500 mt-0.5" />
                                                ) : (
                                                    <Info className="h-5 w-5 text-blue-500 mt-0.5" />
                                                )}
                                                <div>
                                                    <p className="font-medium">{alerta.mensagem}</p>
                                                    <p className="text-sm text-muted-foreground mt-1">{alerta.acao}</p>
                                                </div>
                                            </div>
                                            <Link to="/configuracoes">
                                                <Button variant="ghost" size="sm" className="gap-1">
                                                    Resolver <ArrowRight className="h-4 w-4" />
                                                </Button>
                                            </Link>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </div>
                )}

                {/* Categories */}
                <div className="space-y-3">
                    <h2 className="font-heading text-lg font-semibold">Detalhamento por Categoria</h2>
                    <div className="grid gap-4">
                        {data?.itens?.map((item, index) => {
                            const CategoryIcon = categoryIcons[item.categoria] || FileText;
                            const link = categoryLinks[item.categoria] || '/dashboard';
                            
                            return (
                                <Card key={index} className="hover:border-primary/50 transition-colors">
                                    <CardContent className="p-6">
                                        <div className="flex items-center justify-between gap-4">
                                            <div className="flex items-center gap-4 flex-1">
                                                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                                                    item.completude >= 90 ? 'bg-emerald-500/20' :
                                                    item.completude >= 70 ? 'bg-blue-500/20' :
                                                    item.completude >= 50 ? 'bg-yellow-500/20' :
                                                    'bg-red-500/20'
                                                }`}>
                                                    <CategoryIcon className={`h-6 w-6 ${
                                                        item.completude >= 90 ? 'text-emerald-500' :
                                                        item.completude >= 70 ? 'text-blue-500' :
                                                        item.completude >= 50 ? 'text-yellow-500' :
                                                        'text-red-500'
                                                    }`} />
                                                </div>
                                                <div className="flex-1">
                                                    <div className="flex items-center justify-between mb-2">
                                                        <h3 className="font-semibold">{item.categoria}</h3>
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-sm text-muted-foreground">
                                                                {item.completos}/{item.total}
                                                            </span>
                                                            <Badge variant={
                                                                item.completude >= 90 ? 'default' :
                                                                item.completude >= 70 ? 'secondary' :
                                                                item.completude >= 50 ? 'outline' :
                                                                'destructive'
                                                            }>
                                                                {item.completude}%
                                                            </Badge>
                                                        </div>
                                                    </div>
                                                    <Progress 
                                                        value={item.completude} 
                                                        className="h-2"
                                                    />
                                                    {item.pendentes && item.pendentes.length > 0 && (
                                                        <p className="text-xs text-muted-foreground mt-2">
                                                            {item.pendentes.length} item(ns) com campos pendentes
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                            <Link to={link}>
                                                <Button variant="ghost" size="icon">
                                                    <ChevronRight className="h-5 w-5" />
                                                </Button>
                                            </Link>
                                        </div>
                                    </CardContent>
                                </Card>
                            );
                        })}
                    </div>
                </div>

                {/* Help Section */}
                <Card className="bg-muted/30">
                    <CardContent className="p-6">
                        <div className="flex items-start gap-4">
                            <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center">
                                <FileText className="h-6 w-6 text-primary" />
                            </div>
                            <div className="flex-1">
                                <h3 className="font-heading text-lg font-semibold mb-2">
                                    Sobre a PrestaÃ§Ã£o de Contas Eleitoral
                                </h3>
                                <p className="text-sm text-muted-foreground mb-4">
                                    A prestaÃ§Ã£o de contas deve ser enviada ao TSE atravÃ©s do Sistema de PrestaÃ§Ã£o de Contas 
                                    Eleitorais (SPCE) atÃ© 30 dias apÃ³s as eleiÃ§Ãµes. Todos os campos obrigatÃ³rios devem estar 
                                    preenchidos conforme a ResoluÃ§Ã£o TSE nÂº 23.607/2019.
                                </p>
                                <div className="flex gap-3">
                                    <Button variant="outline" size="sm" asChild>
                                        <a href="https://www.tse.jus.br/eleicoes/eleicoes-2024/prestacao-de-contas" target="_blank" rel="noreferrer">
                                            Manual TSE
                                        </a>
                                    </Button>
                                    <Link to="/assistente">
                                        <Button variant="outline" size="sm">
                                            Perguntar à Flora
                                        </Button>
                                    </Link>
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </Layout>
    );
}

