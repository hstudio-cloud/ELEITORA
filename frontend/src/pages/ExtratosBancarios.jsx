import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { toast } from 'sonner';
import { formatCurrency, formatDate } from '../lib/utils';
import { 
    Upload, FileText, RefreshCw, CheckCircle2, Clock, AlertTriangle, 
    X, ArrowUpRight, ArrowDownRight, Link2, Trash2, Plus, Eye, 
    Banknote, TrendingUp, TrendingDown, FileWarning
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const statusConfig = {
    pending: { 
        label: 'Pendente', 
        color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
        icon: Clock 
    },
    reconciled: { 
        label: 'Conciliado', 
        color: 'bg-green-500/20 text-green-400 border-green-500/30',
        icon: CheckCircle2 
    },
    manual: { 
        label: 'Manual', 
        color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        icon: Link2 
    },
    divergent: { 
        label: 'Divergente', 
        color: 'bg-red-500/20 text-red-400 border-red-500/30',
        icon: AlertTriangle 
    },
    ignored: { 
        label: 'Ignorado', 
        color: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
        icon: X 
    }
};

const revenueCategories = [
    { value: 'doacao_pf', label: 'Doação Pessoa Física' },
    { value: 'doacao_pj', label: 'Doação Pessoa Jurídica' },
    { value: 'recursos_proprios', label: 'Recursos Próprios' },
    { value: 'fundo_eleitoral', label: 'Fundo Eleitoral' },
    { value: 'outros', label: 'Outros' }
];

const expenseCategories = [
    { value: 'publicidade', label: 'Publicidade' },
    { value: 'material_grafico', label: 'Material Gráfico' },
    { value: 'servicos_terceiros', label: 'Serviços de Terceiros' },
    { value: 'transporte', label: 'Transporte' },
    { value: 'alimentacao', label: 'Alimentação' },
    { value: 'pessoal', label: 'Pessoal' },
    { value: 'outros', label: 'Outros' }
];

export default function ExtratosBancarios() {
    const [statements, setStatements] = useState([]);
    const [selectedStatement, setSelectedStatement] = useState(null);
    const [transactions, setTransactions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [reconciling, setReconciling] = useState(false);
    const [showUploadDialog, setShowUploadDialog] = useState(false);
    const [showCreateDialog, setShowCreateDialog] = useState(false);
    const [selectedTransaction, setSelectedTransaction] = useState(null);
    const [newRecordCategory, setNewRecordCategory] = useState('outros');
    const [revenues, setRevenues] = useState([]);
    const [expenses, setExpenses] = useState([]);
    const [showManualDialog, setShowManualDialog] = useState(false);
    const [manualRecordType, setManualRecordType] = useState('');
    const [manualRecordId, setManualRecordId] = useState('');

    useEffect(() => {
        fetchStatements();
        fetchRevenuesAndExpenses();
    }, []);

    const fetchStatements = async () => {
        try {
            const response = await axios.get(`${API}/bank-statements`);
            setStatements(response.data);
        } catch (error) {
            toast.error('Erro ao carregar extratos');
        } finally {
            setLoading(false);
        }
    };

    const fetchRevenuesAndExpenses = async () => {
        try {
            const [revRes, expRes] = await Promise.all([
                axios.get(`${API}/revenues`),
                axios.get(`${API}/expenses`)
            ]);
            setRevenues(revRes.data);
            setExpenses(expRes.data);
        } catch (error) {
            console.error('Error fetching records:', error);
        }
    };

    const fetchTransactions = async (statementId) => {
        try {
            const response = await axios.get(`${API}/bank-statements/${statementId}`);
            setSelectedStatement(response.data.statement);
            setTransactions(response.data.transactions);
        } catch (error) {
            toast.error('Erro ao carregar transações');
        }
    };

    const handleFileUpload = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        if (!file.name.toLowerCase().endsWith('.ofx') && !file.name.toLowerCase().endsWith('.qfx')) {
            toast.error('Formato inválido. Use arquivos .ofx ou .qfx');
            return;
        }

        setUploading(true);
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await axios.post(`${API}/bank-statements/upload`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            toast.success(response.data.message);
            setShowUploadDialog(false);
            fetchStatements();
            
            // Auto-select and reconcile new statement
            if (response.data.statement) {
                setSelectedStatement(response.data.statement);
                setTransactions(response.data.transactions || []);
                
                // Auto reconcile
                handleAutoReconcile(response.data.statement.id);
            }
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao importar extrato');
        } finally {
            setUploading(false);
        }
    };

    const handleAutoReconcile = async (statementId) => {
        setReconciling(true);
        try {
            const response = await axios.post(`${API}/bank-statements/${statementId}/reconcile`);
            toast.success(response.data.message);
            fetchTransactions(statementId);
            fetchStatements();
        } catch (error) {
            toast.error('Erro ao conciliar transações');
        } finally {
            setReconciling(false);
        }
    };

    const handleIgnoreTransaction = async (transactionId) => {
        try {
            await axios.post(`${API}/bank-transactions/${transactionId}/ignore`);
            toast.success('Transação ignorada');
            if (selectedStatement) {
                fetchTransactions(selectedStatement.id);
                fetchStatements();
            }
        } catch (error) {
            toast.error('Erro ao ignorar transação');
        }
    };

    const handleCreateRecord = async () => {
        if (!selectedTransaction) return;

        try {
            const response = await axios.post(
                `${API}/bank-transactions/${selectedTransaction.id}/create-record`,
                null,
                { params: { category: newRecordCategory } }
            );
            toast.success(response.data.message);
            setShowCreateDialog(false);
            setSelectedTransaction(null);
            if (selectedStatement) {
                fetchTransactions(selectedStatement.id);
                fetchStatements();
            }
            fetchRevenuesAndExpenses();
        } catch (error) {
            toast.error('Erro ao criar registro');
        }
    };

    const handleManualReconcile = async () => {
        if (!selectedTransaction || !manualRecordId || !manualRecordType) {
            toast.error('Selecione um registro para conciliar');
            return;
        }

        try {
            await axios.post(
                `${API}/bank-transactions/${selectedTransaction.id}/reconcile-manual`,
                null,
                { params: { record_id: manualRecordId, record_type: manualRecordType } }
            );
            toast.success('Transação conciliada manualmente');
            setShowManualDialog(false);
            setSelectedTransaction(null);
            setManualRecordId('');
            setManualRecordType('');
            if (selectedStatement) {
                fetchTransactions(selectedStatement.id);
                fetchStatements();
            }
        } catch (error) {
            toast.error('Erro ao conciliar transação');
        }
    };

    const handleDeleteStatement = async (statementId) => {
        if (!window.confirm('Tem certeza que deseja excluir este extrato e todas as transações?')) return;

        try {
            await axios.delete(`${API}/bank-statements/${statementId}`);
            toast.success('Extrato excluído');
            if (selectedStatement?.id === statementId) {
                setSelectedStatement(null);
                setTransactions([]);
            }
            fetchStatements();
        } catch (error) {
            toast.error('Erro ao excluir extrato');
        }
    };

    const openCreateDialog = (transaction) => {
        setSelectedTransaction(transaction);
        setNewRecordCategory(transaction.type === 'credit' ? 'doacao_pf' : 'publicidade');
        setShowCreateDialog(true);
    };

    const openManualDialog = (transaction) => {
        setSelectedTransaction(transaction);
        setManualRecordType(transaction.type === 'credit' ? 'revenue' : 'expense');
        setManualRecordId('');
        setShowManualDialog(true);
    };

    const pendingCount = transactions.filter(t => t.reconciliation_status === 'pending').length;
    const reconciledCount = transactions.filter(t => ['reconciled', 'manual'].includes(t.reconciliation_status)).length;

    return (
        <Layout>
            <div className="space-y-6" data-testid="extratos-page">
                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div>
                        <h1 className="font-heading text-3xl font-bold">Extratos Bancários</h1>
                        <p className="text-muted-foreground">Importe extratos OFX e concilie com receitas e despesas</p>
                    </div>
                    <Button className="gap-2" onClick={() => setShowUploadDialog(true)} data-testid="upload-btn">
                        <Upload className="h-4 w-4" />
                        Importar Extrato OFX
                    </Button>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Statements List */}
                    <Card className="lg:col-span-1">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Banknote className="h-5 w-5" />
                                Extratos Importados
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {loading ? (
                                <div className="text-center py-8 text-muted-foreground">Carregando...</div>
                            ) : statements.length === 0 ? (
                                <div className="text-center py-8">
                                    <FileWarning className="h-12 w-12 mx-auto text-muted-foreground mb-2" />
                                    <p className="text-muted-foreground">Nenhum extrato importado</p>
                                    <Button 
                                        variant="outline" 
                                        size="sm" 
                                        className="mt-4"
                                        onClick={() => setShowUploadDialog(true)}
                                    >
                                        <Upload className="h-4 w-4 mr-2" />
                                        Importar primeiro extrato
                                    </Button>
                                </div>
                            ) : (
                                <div className="space-y-3">
                                    {statements.map((stmt) => (
                                        <div
                                            key={stmt.id}
                                            className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                                                selectedStatement?.id === stmt.id
                                                    ? 'border-primary bg-primary/5'
                                                    : 'border-border hover:border-primary/50'
                                            }`}
                                            onClick={() => fetchTransactions(stmt.id)}
                                            data-testid={`statement-${stmt.id}`}
                                        >
                                            <div className="flex justify-between items-start">
                                                <div>
                                                    <p className="font-medium">{stmt.bank_name}</p>
                                                    <p className="text-sm text-muted-foreground">
                                                        Conta: {stmt.account_number}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground mt-1">
                                                        {formatDate(stmt.start_date)} - {formatDate(stmt.end_date)}
                                                    </p>
                                                </div>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="text-destructive"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleDeleteStatement(stmt.id);
                                                    }}
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            </div>
                                            <div className="mt-3 flex items-center gap-4 text-sm">
                                                <span className="text-green-400">
                                                    <TrendingUp className="h-3 w-3 inline mr-1" />
                                                    {formatCurrency(stmt.total_credits)}
                                                </span>
                                                <span className="text-red-400">
                                                    <TrendingDown className="h-3 w-3 inline mr-1" />
                                                    {formatCurrency(stmt.total_debits)}
                                                </span>
                                            </div>
                                            <div className="mt-2">
                                                <div className="flex justify-between text-xs text-muted-foreground mb-1">
                                                    <span>{stmt.reconciled_count}/{stmt.transaction_count} conciliados</span>
                                                    <span>{Math.round((stmt.reconciled_count / stmt.transaction_count) * 100)}%</span>
                                                </div>
                                                <Progress 
                                                    value={(stmt.reconciled_count / stmt.transaction_count) * 100} 
                                                    className="h-1.5"
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Transactions */}
                    <Card className="lg:col-span-2">
                        <CardHeader>
                            <div className="flex justify-between items-center">
                                <div>
                                    <CardTitle>Transações</CardTitle>
                                    {selectedStatement && (
                                        <CardDescription>
                                            {selectedStatement.bank_name} - {pendingCount} pendentes, {reconciledCount} conciliados
                                        </CardDescription>
                                    )}
                                </div>
                                {selectedStatement && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleAutoReconcile(selectedStatement.id)}
                                        disabled={reconciling}
                                        className="gap-2"
                                        data-testid="reconcile-btn"
                                    >
                                        <RefreshCw className={`h-4 w-4 ${reconciling ? 'animate-spin' : ''}`} />
                                        {reconciling ? 'Conciliando...' : 'Reconciliar'}
                                    </Button>
                                )}
                            </div>
                        </CardHeader>
                        <CardContent>
                            {!selectedStatement ? (
                                <div className="text-center py-12 text-muted-foreground">
                                    <Eye className="h-12 w-12 mx-auto mb-2" />
                                    <p>Selecione um extrato para ver as transações</p>
                                </div>
                            ) : transactions.length === 0 ? (
                                <div className="text-center py-12 text-muted-foreground">
                                    Nenhuma transação encontrada
                                </div>
                            ) : (
                                <div className="overflow-x-auto">
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Data</TableHead>
                                                <TableHead>Descrição</TableHead>
                                                <TableHead className="text-right">Valor</TableHead>
                                                <TableHead>Status</TableHead>
                                                <TableHead className="w-32">Ações</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {transactions.map((txn) => {
                                                const status = statusConfig[txn.reconciliation_status] || statusConfig.pending;
                                                const StatusIcon = status.icon;
                                                return (
                                                    <TableRow key={txn.id} data-testid={`txn-${txn.id}`}>
                                                        <TableCell className="font-mono text-sm">
                                                            {formatDate(txn.date)}
                                                        </TableCell>
                                                        <TableCell>
                                                            <div>
                                                                <p className="font-medium text-sm">{txn.description}</p>
                                                                {txn.payee && txn.payee !== txn.description && (
                                                                    <p className="text-xs text-muted-foreground">{txn.payee}</p>
                                                                )}
                                                            </div>
                                                        </TableCell>
                                                        <TableCell className="text-right">
                                                            <span className={`font-mono font-medium ${
                                                                txn.type === 'credit' ? 'text-green-400' : 'text-red-400'
                                                            }`}>
                                                                {txn.type === 'credit' ? (
                                                                    <ArrowUpRight className="h-3 w-3 inline mr-1" />
                                                                ) : (
                                                                    <ArrowDownRight className="h-3 w-3 inline mr-1" />
                                                                )}
                                                                {formatCurrency(txn.amount)}
                                                            </span>
                                                        </TableCell>
                                                        <TableCell>
                                                            <Badge className={`gap-1 ${status.color}`}>
                                                                <StatusIcon className="h-3 w-3" />
                                                                {status.label}
                                                            </Badge>
                                                            {txn.match_confidence > 0 && (
                                                                <p className="text-xs text-muted-foreground mt-1">
                                                                    {txn.match_confidence}% confiança
                                                                </p>
                                                            )}
                                                        </TableCell>
                                                        <TableCell>
                                                            {txn.reconciliation_status === 'pending' && (
                                                                <div className="flex gap-1">
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="icon"
                                                                        title="Criar receita/despesa"
                                                                        onClick={() => openCreateDialog(txn)}
                                                                        data-testid={`create-${txn.id}`}
                                                                    >
                                                                        <Plus className="h-4 w-4" />
                                                                    </Button>
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="icon"
                                                                        title="Vincular manualmente"
                                                                        onClick={() => openManualDialog(txn)}
                                                                        data-testid={`link-${txn.id}`}
                                                                    >
                                                                        <Link2 className="h-4 w-4" />
                                                                    </Button>
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="icon"
                                                                        title="Ignorar"
                                                                        onClick={() => handleIgnoreTransaction(txn.id)}
                                                                        className="text-muted-foreground"
                                                                        data-testid={`ignore-${txn.id}`}
                                                                    >
                                                                        <X className="h-4 w-4" />
                                                                    </Button>
                                                                </div>
                                                            )}
                                                        </TableCell>
                                                    </TableRow>
                                                );
                                            })}
                                        </TableBody>
                                    </Table>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Upload Dialog */}
                <Dialog open={showUploadDialog} onOpenChange={setShowUploadDialog}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Importar Extrato Bancário</DialogTitle>
                            <DialogDescription>
                                Selecione um arquivo OFX ou QFX do seu banco
                            </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 mt-4">
                            <div className="border-2 border-dashed border-border rounded-lg p-8 text-center">
                                <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                                <p className="text-muted-foreground mb-4">
                                    Arraste um arquivo OFX/QFX ou clique para selecionar
                                </p>
                                <label className="cursor-pointer">
                                    <input
                                        type="file"
                                        accept=".ofx,.qfx"
                                        className="hidden"
                                        onChange={handleFileUpload}
                                        disabled={uploading}
                                    />
                                    <Button disabled={uploading} data-testid="select-file-btn">
                                        {uploading ? 'Importando...' : 'Selecionar Arquivo'}
                                    </Button>
                                </label>
                            </div>
                            <div className="text-sm text-muted-foreground">
                                <p><strong>Formatos suportados:</strong> OFX, QFX (Open Financial Exchange)</p>
                                <p className="mt-1">A maioria dos bancos brasileiros permite exportar extratos neste formato.</p>
                            </div>
                        </div>
                    </DialogContent>
                </Dialog>

                {/* Create Record Dialog */}
                <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>
                                Criar {selectedTransaction?.type === 'credit' ? 'Receita' : 'Despesa'}
                            </DialogTitle>
                            <DialogDescription>
                                Criar um registro a partir desta transação bancária
                            </DialogDescription>
                        </DialogHeader>
                        {selectedTransaction && (
                            <div className="space-y-4 mt-4">
                                <div className="p-4 bg-muted rounded-lg">
                                    <p className="text-sm text-muted-foreground">Transação</p>
                                    <p className="font-medium">{selectedTransaction.description}</p>
                                    <p className={`font-mono ${
                                        selectedTransaction.type === 'credit' ? 'text-green-400' : 'text-red-400'
                                    }`}>
                                        {formatCurrency(selectedTransaction.amount)}
                                    </p>
                                    <p className="text-sm text-muted-foreground">{formatDate(selectedTransaction.date)}</p>
                                </div>
                                <div className="space-y-2">
                                    <Label>Categoria</Label>
                                    <Select value={newRecordCategory} onValueChange={setNewRecordCategory}>
                                        <SelectTrigger data-testid="category-select">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {(selectedTransaction.type === 'credit' ? revenueCategories : expenseCategories).map(cat => (
                                                <SelectItem key={cat.value} value={cat.value}>
                                                    {cat.label}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="flex justify-end gap-3">
                                    <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                                        Cancelar
                                    </Button>
                                    <Button onClick={handleCreateRecord} data-testid="confirm-create-btn">
                                        Criar {selectedTransaction.type === 'credit' ? 'Receita' : 'Despesa'}
                                    </Button>
                                </div>
                            </div>
                        )}
                    </DialogContent>
                </Dialog>

                {/* Manual Reconciliation Dialog */}
                <Dialog open={showManualDialog} onOpenChange={setShowManualDialog}>
                    <DialogContent className="max-w-2xl">
                        <DialogHeader>
                            <DialogTitle>Conciliação Manual</DialogTitle>
                            <DialogDescription>
                                Vincular transação a uma receita ou despesa existente
                            </DialogDescription>
                        </DialogHeader>
                        {selectedTransaction && (
                            <div className="space-y-4 mt-4">
                                <div className="p-4 bg-muted rounded-lg">
                                    <p className="text-sm text-muted-foreground">Transação</p>
                                    <p className="font-medium">{selectedTransaction.description}</p>
                                    <p className={`font-mono ${
                                        selectedTransaction.type === 'credit' ? 'text-green-400' : 'text-red-400'
                                    }`}>
                                        {formatCurrency(selectedTransaction.amount)}
                                    </p>
                                </div>
                                
                                <div className="space-y-2">
                                    <Label>Tipo de Registro</Label>
                                    <Select value={manualRecordType} onValueChange={setManualRecordType}>
                                        <SelectTrigger>
                                            <SelectValue placeholder="Selecione o tipo" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="revenue">Receita</SelectItem>
                                            <SelectItem value="expense">Despesa</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                {manualRecordType && (
                                    <div className="space-y-2">
                                        <Label>Selecione o Registro</Label>
                                        <Select value={manualRecordId} onValueChange={setManualRecordId}>
                                            <SelectTrigger>
                                                <SelectValue placeholder="Selecione..." />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {(manualRecordType === 'revenue' ? revenues : expenses).map(rec => (
                                                    <SelectItem key={rec.id} value={rec.id}>
                                                        {rec.description} - {formatCurrency(rec.amount)} ({formatDate(rec.date)})
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                )}

                                <div className="flex justify-end gap-3">
                                    <Button variant="outline" onClick={() => setShowManualDialog(false)}>
                                        Cancelar
                                    </Button>
                                    <Button 
                                        onClick={handleManualReconcile} 
                                        disabled={!manualRecordId}
                                        data-testid="confirm-manual-btn"
                                    >
                                        Conciliar
                                    </Button>
                                </div>
                            </div>
                        )}
                    </DialogContent>
                </Dialog>
            </div>
        </Layout>
    );
}
