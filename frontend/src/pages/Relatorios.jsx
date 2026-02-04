import { useState, useEffect } from 'react';
import axios from 'axios';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import { formatCurrency, formatDate, categoryLabels } from '../lib/utils';
import { Download, FileText, BarChart3, Calendar, RefreshCw, FileCode, AlertCircle } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Relatorios() {
    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchReport();
    }, []);

    const fetchReport = async () => {
        setLoading(true);
        try {
            const response = await axios.get(`${API}/reports/tse`);
            setReport(response.data);
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao gerar relatório');
        } finally {
            setLoading(false);
        }
    };

    const handleExportJSON = () => {
        if (!report) return;
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `relatorio_tse_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
        toast.success('Relatório exportado com sucesso!');
    };

    const handleExportCSV = (type) => {
        if (!report) return;
        
        let data, headers, filename;
        
        if (type === 'receitas') {
            data = report.receitas;
            headers = ['Data', 'Descrição', 'Valor', 'Categoria', 'Doador', 'CPF/CNPJ', 'Recibo'];
            filename = 'receitas_tse.csv';
        } else {
            data = report.despesas;
            headers = ['Data', 'Descrição', 'Valor', 'Categoria', 'Fornecedor', 'CPF/CNPJ', 'Nota Fiscal'];
            filename = 'despesas_tse.csv';
        }

        const csvContent = [
            headers.join(';'),
            ...data.map(item => [
                item.data,
                `"${item.descricao}"`,
                item.valor.toFixed(2).replace('.', ','),
                categoryLabels[item.categoria] || item.categoria,
                `"${item.doador || item.fornecedor || ''}"`,
                item.cpf_cnpj || '',
                item.recibo || item.nota_fiscal || ''
            ].join(';'))
        ].join('\n');

        const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
        toast.success('Exportação concluída!');
    };

    const handleExportSPCE = async () => {
        try {
            const response = await axios.get(`${API}/export/spce-doacoes`);
            const { filename, content, total_doacoes } = response.data;
            
            const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
            
            toast.success(`Arquivo SPCE exportado! ${total_doacoes} doações.`);
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao exportar SPCE. Verifique se o CNPJ e contas bancárias estão configurados.');
        }
    };

    return (
        <Layout>
            <div className="space-y-6" data-testid="relatorios-page">
                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div>
                        <h1 className="font-heading text-3xl font-bold">Relatórios e Exportação</h1>
                        <p className="text-muted-foreground">Gere relatórios e exporte para o SPCE da Justiça Eleitoral</p>
                    </div>
                    <div className="flex gap-3">
                        <Button
                            variant="outline"
                            onClick={fetchReport}
                            disabled={loading}
                            className="gap-2"
                            data-testid="refresh-report-btn"
                        >
                            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                            Atualizar
                        </Button>
                    </div>
                </div>

                <Tabs defaultValue="relatorio" className="space-y-6">
                    <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="relatorio">Relatório Geral</TabsTrigger>
                        <TabsTrigger value="spce">Exportação SPCE</TabsTrigger>
                    </TabsList>

                    {/* Relatório Tab */}
                    <TabsContent value="relatorio">
                        {loading ? (
                            <div className="text-center py-20 text-muted-foreground">
                                <RefreshCw className="h-8 w-8 animate-spin mx-auto mb-4" />
                                <p>Gerando relatório...</p>
                            </div>
                        ) : !report ? (
                            <Card>
                                <CardContent className="py-20 text-center">
                                    <FileText className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
                                    <p className="text-muted-foreground">
                                        Configure uma campanha para gerar relatórios
                                    </p>
                                </CardContent>
                            </Card>
                ) : (
                    <>
                        {/* Campaign Info */}
                        {report.campanha && (
                            <Card data-testid="campaign-info-card">
                                <CardHeader>
                                    <CardTitle className="font-heading flex items-center gap-2">
                                        <FileText className="h-5 w-5" />
                                        Informações da Campanha
                                    </CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                                        <div>
                                            <p className="text-sm text-muted-foreground">Candidato</p>
                                            <p className="font-semibold">{report.campanha.candidate_name}</p>
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Partido</p>
                                            <p className="font-semibold">{report.campanha.party}</p>
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Cargo</p>
                                            <p className="font-semibold">{report.campanha.position}</p>
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Local</p>
                                            <p className="font-semibold">{report.campanha.city} - {report.campanha.state}</p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* Summary Cards */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <Card className="border-secondary/50" data-testid="total-receitas-card">
                                <CardContent className="p-6">
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 rounded-lg bg-secondary/20 flex items-center justify-center">
                                            <BarChart3 className="h-6 w-6 text-secondary" />
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Total Receitas</p>
                                            <p className="font-heading text-2xl font-bold text-secondary">
                                                {formatCurrency(report.totais?.total_receitas)}
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            <Card className="border-destructive/50" data-testid="total-despesas-card">
                                <CardContent className="p-6">
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 rounded-lg bg-destructive/20 flex items-center justify-center">
                                            <BarChart3 className="h-6 w-6 text-destructive" />
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Total Despesas</p>
                                            <p className="font-heading text-2xl font-bold text-destructive">
                                                {formatCurrency(report.totais?.total_despesas)}
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            <Card className="border-primary/50" data-testid="saldo-card">
                                <CardContent className="p-6">
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 rounded-lg bg-primary/20 flex items-center justify-center">
                                            <Calendar className="h-6 w-6 text-primary" />
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Saldo</p>
                                            <p className={`font-heading text-2xl font-bold ${report.totais?.saldo >= 0 ? 'text-secondary' : 'text-destructive'}`}>
                                                {formatCurrency(report.totais?.saldo)}
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Receitas Table */}
                        <Card data-testid="receitas-report-card">
                            <CardHeader className="flex flex-row items-center justify-between">
                                <div>
                                    <CardTitle className="font-heading">Receitas</CardTitle>
                                    <CardDescription>{report.receitas?.length || 0} registros</CardDescription>
                                </div>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleExportCSV('receitas')}
                                    className="gap-2"
                                    data-testid="export-receitas-btn"
                                >
                                    <Download className="h-4 w-4" />
                                    CSV
                                </Button>
                            </CardHeader>
                            <CardContent>
                                {report.receitas?.length === 0 ? (
                                    <p className="text-center py-8 text-muted-foreground">Nenhuma receita registrada</p>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Data</TableHead>
                                                    <TableHead>Descrição</TableHead>
                                                    <TableHead>Categoria</TableHead>
                                                    <TableHead>Doador</TableHead>
                                                    <TableHead className="text-right">Valor</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {report.receitas?.map((item, index) => (
                                                    <TableRow key={index}>
                                                        <TableCell className="font-mono text-sm">
                                                            {formatDate(item.data)}
                                                        </TableCell>
                                                        <TableCell>{item.descricao}</TableCell>
                                                        <TableCell>
                                                            <Badge variant="outline">
                                                                {categoryLabels[item.categoria] || item.categoria}
                                                            </Badge>
                                                        </TableCell>
                                                        <TableCell className="text-muted-foreground">
                                                            {item.doador || '-'}
                                                        </TableCell>
                                                        <TableCell className="text-right font-mono text-secondary">
                                                            {formatCurrency(item.valor)}
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Despesas Table */}
                        <Card data-testid="despesas-report-card">
                            <CardHeader className="flex flex-row items-center justify-between">
                                <div>
                                    <CardTitle className="font-heading">Despesas</CardTitle>
                                    <CardDescription>{report.despesas?.length || 0} registros</CardDescription>
                                </div>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleExportCSV('despesas')}
                                    className="gap-2"
                                    data-testid="export-despesas-btn"
                                >
                                    <Download className="h-4 w-4" />
                                    CSV
                                </Button>
                            </CardHeader>
                            <CardContent>
                                {report.despesas?.length === 0 ? (
                                    <p className="text-center py-8 text-muted-foreground">Nenhuma despesa registrada</p>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Data</TableHead>
                                                    <TableHead>Descrição</TableHead>
                                                    <TableHead>Categoria</TableHead>
                                                    <TableHead>Fornecedor</TableHead>
                                                    <TableHead className="text-right">Valor</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {report.despesas?.map((item, index) => (
                                                    <TableRow key={index}>
                                                        <TableCell className="font-mono text-sm">
                                                            {formatDate(item.data)}
                                                        </TableCell>
                                                        <TableCell>{item.descricao}</TableCell>
                                                        <TableCell>
                                                            <Badge variant="outline">
                                                                {categoryLabels[item.categoria] || item.categoria}
                                                            </Badge>
                                                        </TableCell>
                                                        <TableCell className="text-muted-foreground">
                                                            {item.fornecedor || '-'}
                                                        </TableCell>
                                                        <TableCell className="text-right font-mono text-destructive">
                                                            {formatCurrency(item.valor)}
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Report metadata */}
                        <div className="text-center text-sm text-muted-foreground">
                            Relatório gerado em: {formatDate(report.gerado_em)} às {new Date(report.gerado_em).toLocaleTimeString('pt-BR')}
                        </div>
                    </>
                )}
            </div>
        </Layout>
    );
}
