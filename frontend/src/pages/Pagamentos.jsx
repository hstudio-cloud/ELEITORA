import { useState, useEffect } from 'react';
import axios from 'axios';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Progress } from '../components/ui/progress';
import { toast } from 'sonner';
import { formatCurrency, formatDate, statusLabels, statusColors } from '../lib/utils';
import { 
    Plus, Pencil, Trash2, CreditCard, Search, Clock, CheckCircle, 
    Banknote, QrCode, Send, AlertCircle, Building2, RefreshCw,
    Calendar, User, Phone, Mail, Hash, Copy, ExternalLink
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const paymentStatuses = [
    { value: 'pendente', label: 'Pendente' },
    { value: 'pago', label: 'Pago' },
    { value: 'cancelado', label: 'Cancelado' }
];

const pixKeyTypes = [
    { value: 'cpf', label: 'CPF', icon: User, placeholder: '000.000.000-00' },
    { value: 'cnpj', label: 'CNPJ', icon: Building2, placeholder: '00.000.000/0000-00' },
    { value: 'email', label: 'E-mail', icon: Mail, placeholder: 'email@exemplo.com' },
    { value: 'phone', label: 'Telefone', icon: Phone, placeholder: '+55 84 99999-0000' },
    { value: 'random', label: 'Chave Aleatória', icon: Hash, placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx' }
];

const pixStatuses = {
    agendado: { label: 'Agendado', color: 'bg-blue-500/20 text-blue-500 border-blue-500/30' },
    processando: { label: 'Processando', color: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30' },
    executado: { label: 'Executado', color: 'bg-emerald-500/20 text-emerald-500 border-emerald-500/30' },
    falhou: { label: 'Falhou', color: 'bg-red-500/20 text-red-500 border-red-500/30' },
    cancelado: { label: 'Cancelado', color: 'bg-gray-500/20 text-gray-500 border-gray-500/30' }
};

const pixSourceAccounts = [
    { value: 'doacao', label: 'Conta de Doacao (Outros Recursos)' },
    { value: 'fundo_partidario', label: 'Conta Fundo Partidario' },
    { value: 'fefec', label: 'Conta FEFEC (Fundo Eleitoral)' }
];
const pixSourceAccountLabels = Object.fromEntries(pixSourceAccounts.map(item => [item.value, item.label]));

const emptyForm = {
    description: '',
    amount: '',
    due_date: new Date().toISOString().split('T')[0],
    payment_date: '',
    status: 'pendente',
    expense_id: '',
    contract_id: '',
    notes: ''
};

const emptyPixForm = {
    source_account_type: 'doacao',
    pix_key: '',
    pix_key_type: 'cpf',
    recipient_name: '',
    recipient_cpf_cnpj: '',
    amount: '',
    description: '',
    scheduled_date: new Date().toISOString().split('T')[0],
    expense_id: ''
};

export default function Pagamentos() {
    const [payments, setPayments] = useState([]);
    const [pixPayments, setPixPayments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [pixDialogOpen, setPixDialogOpen] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [formData, setFormData] = useState(emptyForm);
    const [pixFormData, setPixFormData] = useState(emptyPixForm);
    const [searchTerm, setSearchTerm] = useState('');
    const [saving, setSaving] = useState(false);
    const [activeTab, setActiveTab] = useState('pagamentos');
    const [bankInfo, setBankInfo] = useState(null);
    const [selectedPixPayment, setSelectedPixPayment] = useState(null);
    const [expenses, setExpenses] = useState([]);

    useEffect(() => {
        fetchPayments();
        fetchPixPayments();
        fetchBankInfo();
        fetchExpenses();
    }, []);

    const fetchPayments = async () => {
        try {
            const response = await axios.get(`${API}/payments`);
            setPayments(response.data);
        } catch (error) {
            toast.error('Erro ao carregar pagamentos');
        } finally {
            setLoading(false);
        }
    };

    const fetchPixPayments = async () => {
        try {
            const response = await axios.get(`${API}/pix/payments`);
            setPixPayments(response.data || []);
        } catch (error) {
            console.error('Erro ao carregar PIX:', error);
        }
    };

    const fetchBankInfo = async () => {
        try {
            const response = await axios.get(`${API}/pix/bank-info`);
            setBankInfo(response.data);
        } catch (error) {
            console.error('Erro ao carregar info do banco:', error);
        }
    };

    const fetchExpenses = async () => {
        try {
            const response = await axios.get(`${API}/expenses`);
            setExpenses(response.data.filter(e => e.payment_status === 'pendente'));
        } catch (error) {
            console.error('Erro ao carregar despesas:', error);
        }
    };

    const handleChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const handlePixChange = (field, value) => {
        setPixFormData(prev => ({ ...prev, [field]: value }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);

        try {
            const payload = {
                ...formData,
                amount: parseFloat(formData.amount),
                expense_id: formData.expense_id || null,
                contract_id: formData.contract_id || null,
                payment_date: formData.payment_date || null
            };

            if (editingId) {
                await axios.put(`${API}/payments/${editingId}`, payload);
                toast.success('Pagamento atualizado!');
            } else {
                await axios.post(`${API}/payments`, payload);
                toast.success('Pagamento cadastrado!');
            }

            setDialogOpen(false);
            setEditingId(null);
            setFormData(emptyForm);
            fetchPayments();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao salvar pagamento');
        } finally {
            setSaving(false);
        }
    };

    const handlePixSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);

        try {
            const payload = {
                ...pixFormData,
                amount: parseFloat(pixFormData.amount),
                expense_id: pixFormData.expense_id || null
            };

            const response = await axios.post(`${API}/pix/payment`, payload);
            toast.success('Pagamento PIX agendado com sucesso!');
            
            setPixDialogOpen(false);
            setPixFormData(emptyPixForm);
            fetchPixPayments();
            
            // Show the created payment details
            if (response.data.pix_payment) {
                setSelectedPixPayment(response.data.pix_payment);
            }
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao agendar PIX');
        } finally {
            setSaving(false);
        }
    };

    const handleEdit = (payment) => {
        setFormData({
            description: payment.description,
            amount: payment.amount.toString(),
            due_date: payment.due_date,
            payment_date: payment.payment_date || '',
            status: payment.status,
            expense_id: payment.expense_id || '',
            contract_id: payment.contract_id || '',
            notes: payment.notes || ''
        });
        setEditingId(payment.id);
        setDialogOpen(true);
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Tem certeza que deseja excluir este pagamento?')) return;

        try {
            await axios.delete(`${API}/payments/${id}`);
            toast.success('Pagamento excluído!');
            fetchPayments();
        } catch (error) {
            toast.error('Erro ao excluir pagamento');
        }
    };

    const handleMarkAsPaid = async (payment) => {
        try {
            const payload = {
                description: payment.description,
                amount: payment.amount,
                due_date: payment.due_date,
                payment_date: new Date().toISOString().split('T')[0],
                status: 'pago',
                expense_id: payment.expense_id,
                contract_id: payment.contract_id,
                notes: payment.notes
            };
            await axios.put(`${API}/payments/${payment.id}`, payload);
            toast.success('Pagamento marcado como pago!');
            fetchPayments();
        } catch (error) {
            toast.error('Erro ao atualizar pagamento');
        }
    };

    const handleSimulatePix = async (pixId) => {
        try {
            const response = await axios.post(`${API}/pix/simulate-execution/${pixId}`);
            toast.success('PIX executado com sucesso (simulação)!');
            fetchPixPayments();
            fetchExpenses();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao executar PIX');
        }
    };

    const copyToClipboard = (text) => {
        navigator.clipboard.writeText(text);
        toast.success('Copiado para a área de transferência!');
    };

    const filteredPayments = payments.filter(p =>
        p.description.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const filteredPixPayments = pixPayments.filter(p =>
        p.recipient_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.description?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const totalPayments = filteredPayments.reduce((sum, p) => sum + p.amount, 0);
    const pendingPayments = filteredPayments.filter(p => p.status === 'pendente');
    const pendingTotal = pendingPayments.reduce((sum, p) => sum + p.amount, 0);

    const totalPixAgendado = filteredPixPayments
        .filter(p => p.status === 'agendado')
        .reduce((sum, p) => sum + p.amount, 0);
    const totalPixExecutado = filteredPixPayments
        .filter(p => p.status === 'executado')
        .reduce((sum, p) => sum + p.amount, 0);

    const selectedKeyType = pixKeyTypes.find(t => t.pix_key_type === pixFormData.pix_key_type) || pixKeyTypes[0];

    return (
        <Layout>
            <div className="space-y-6" data-testid="pagamentos-page">
                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div>
                        <h1 className="font-heading text-3xl font-bold">Pagamentos</h1>
                        <p className="text-muted-foreground">Controle os pagamentos da campanha</p>
                    </div>
                </div>

                {/* Tabs */}
                <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
                    <TabsList className="grid w-full max-w-md grid-cols-2">
                        <TabsTrigger value="pagamentos" className="gap-2" data-testid="tab-pagamentos">
                            <CreditCard className="h-4 w-4" />
                            Pagamentos
                        </TabsTrigger>
                        <TabsTrigger value="pix" className="gap-2" data-testid="tab-pix">
                            <QrCode className="h-4 w-4" />
                            PIX
                        </TabsTrigger>
                    </TabsList>

                    {/* TAB: Pagamentos Tradicionais */}
                    <TabsContent value="pagamentos" className="space-y-6">
                        {/* Summary Cards */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <Card data-testid="payment-total-card">
                                <CardContent className="p-6">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-4">
                                            <div className="w-14 h-14 rounded-xl bg-primary/20 flex items-center justify-center">
                                                <CreditCard className="h-7 w-7 text-primary" />
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Total em Pagamentos</p>
                                                <p className="font-heading text-3xl font-bold">
                                                    {formatCurrency(totalPayments)}
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card data-testid="payment-pending-card">
                                <CardContent className="p-6">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-4">
                                            <div className="w-14 h-14 rounded-xl bg-accent/20 flex items-center justify-center">
                                                <Clock className="h-7 w-7 text-accent" />
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Pendentes</p>
                                                <p className="font-heading text-3xl font-bold text-accent">
                                                    {formatCurrency(pendingTotal)}
                                                </p>
                                            </div>
                                        </div>
                                        <Badge variant="outline" className="text-lg px-4 py-2 border-accent text-accent">
                                            {pendingPayments.length} pendentes
                                        </Badge>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Payments Table */}
                        <Card>
                            <CardHeader className="pb-4">
                                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                                    <CardTitle className="font-heading">Lista de Pagamentos</CardTitle>
                                    <div className="flex gap-3">
                                        <div className="relative w-full md:w-80">
                                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                            <Input
                                                placeholder="Buscar por descrição..."
                                                value={searchTerm}
                                                onChange={(e) => setSearchTerm(e.target.value)}
                                                className="pl-10"
                                                data-testid="payment-search-input"
                                            />
                                        </div>
                                        <Dialog open={dialogOpen} onOpenChange={(open) => {
                                            setDialogOpen(open);
                                            if (!open) {
                                                setEditingId(null);
                                                setFormData(emptyForm);
                                            }
                                        }}>
                                            <DialogTrigger asChild>
                                                <Button className="gap-2" data-testid="add-payment-btn">
                                                    <Plus className="h-4 w-4" />
                                                    Novo Pagamento
                                                </Button>
                                            </DialogTrigger>
                                            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                                                <DialogHeader>
                                                    <DialogTitle className="font-heading">
                                                        {editingId ? 'Editar Pagamento' : 'Novo Pagamento'}
                                                    </DialogTitle>
                                                </DialogHeader>
                                                <form onSubmit={handleSubmit} className="space-y-4 mt-4">
                                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                        <div className="space-y-2 md:col-span-2">
                                                            <Label>Descrição *</Label>
                                                            <Input
                                                                value={formData.description}
                                                                onChange={(e) => handleChange('description', e.target.value)}
                                                                required
                                                                data-testid="payment-description-input"
                                                            />
                                                        </div>
                                                        <div className="space-y-2">
                                                            <Label>Valor (R$) *</Label>
                                                            <Input
                                                                type="number"
                                                                step="0.01"
                                                                min="0"
                                                                value={formData.amount}
                                                                onChange={(e) => handleChange('amount', e.target.value)}
                                                                required
                                                                data-testid="payment-amount-input"
                                                            />
                                                        </div>
                                                        <div className="space-y-2">
                                                            <Label>Status</Label>
                                                            <Select
                                                                value={formData.status}
                                                                onValueChange={(value) => handleChange('status', value)}
                                                            >
                                                                <SelectTrigger data-testid="payment-status-select">
                                                                    <SelectValue />
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    {paymentStatuses.map(status => (
                                                                        <SelectItem key={status.value} value={status.value}>
                                                                            {status.label}
                                                                        </SelectItem>
                                                                    ))}
                                                                </SelectContent>
                                                            </Select>
                                                        </div>
                                                        <div className="space-y-2">
                                                            <Label>Data de Vencimento *</Label>
                                                            <Input
                                                                type="date"
                                                                value={formData.due_date}
                                                                onChange={(e) => handleChange('due_date', e.target.value)}
                                                                required
                                                                data-testid="payment-due-date-input"
                                                            />
                                                        </div>
                                                        <div className="space-y-2">
                                                            <Label>Data de Pagamento</Label>
                                                            <Input
                                                                type="date"
                                                                value={formData.payment_date}
                                                                onChange={(e) => handleChange('payment_date', e.target.value)}
                                                                data-testid="payment-payment-date-input"
                                                            />
                                                        </div>
                                                        <div className="space-y-2 md:col-span-2">
                                                            <Label>Observações</Label>
                                                            <Textarea
                                                                value={formData.notes}
                                                                onChange={(e) => handleChange('notes', e.target.value)}
                                                                rows={3}
                                                                data-testid="payment-notes-input"
                                                            />
                                                        </div>
                                                    </div>
                                                    <div className="flex justify-end gap-3 pt-4">
                                                        <Button
                                                            type="button"
                                                            variant="outline"
                                                            onClick={() => setDialogOpen(false)}
                                                        >
                                                            Cancelar
                                                        </Button>
                                                        <Button type="submit" disabled={saving} data-testid="payment-submit-btn">
                                                            {saving ? 'Salvando...' : editingId ? 'Atualizar' : 'Cadastrar'}
                                                        </Button>
                                                    </div>
                                                </form>
                                            </DialogContent>
                                        </Dialog>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {loading ? (
                                    <div className="text-center py-12 text-muted-foreground">Carregando...</div>
                                ) : filteredPayments.length === 0 ? (
                                    <div className="text-center py-12 text-muted-foreground">
                                        Nenhum pagamento encontrado
                                    </div>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Descrição</TableHead>
                                                    <TableHead>Vencimento</TableHead>
                                                    <TableHead>Pagamento</TableHead>
                                                    <TableHead>Status</TableHead>
                                                    <TableHead className="text-right">Valor</TableHead>
                                                    <TableHead className="w-32">Ações</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {filteredPayments.map((payment) => (
                                                    <TableRow key={payment.id} data-testid={`payment-row-${payment.id}`}>
                                                        <TableCell className="font-medium">
                                                            {payment.description}
                                                        </TableCell>
                                                        <TableCell className="font-mono text-sm">
                                                            {formatDate(payment.due_date)}
                                                        </TableCell>
                                                        <TableCell className="font-mono text-sm">
                                                            {payment.payment_date ? formatDate(payment.payment_date) : '-'}
                                                        </TableCell>
                                                        <TableCell>
                                                            <Badge className={statusColors[payment.status]}>
                                                                {statusLabels[payment.status]}
                                                            </Badge>
                                                        </TableCell>
                                                        <TableCell className="text-right font-semibold">
                                                            {formatCurrency(payment.amount)}
                                                        </TableCell>
                                                        <TableCell>
                                                            <div className="flex items-center gap-1">
                                                                {payment.status === 'pendente' && (
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="icon"
                                                                        className="text-secondary hover:text-secondary"
                                                                        onClick={() => handleMarkAsPaid(payment)}
                                                                        title="Marcar como pago"
                                                                    >
                                                                        <CheckCircle className="h-4 w-4" />
                                                                    </Button>
                                                                )}
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon"
                                                                    onClick={() => handleEdit(payment)}
                                                                    title="Editar"
                                                                >
                                                                    <Pencil className="h-4 w-4" />
                                                                </Button>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon"
                                                                    className="text-destructive hover:text-destructive"
                                                                    onClick={() => handleDelete(payment.id)}
                                                                    title="Excluir"
                                                                >
                                                                    <Trash2 className="h-4 w-4" />
                                                                </Button>
                                                            </div>
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* TAB: PIX */}
                    <TabsContent value="pix" className="space-y-6">
                        {/* PIX Info Banner */}
                        <Card className="border-blue-500/30 bg-gradient-to-br from-blue-500/5 to-blue-600/10">
                            <CardContent className="p-6">
                                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                                    <div className="flex items-center gap-4">
                                        <div className="w-16 h-16 rounded-xl bg-blue-500/20 flex items-center justify-center">
                                            <Banknote className="h-8 w-8 text-blue-500" />
                                        </div>
                                        <div>
                                            <h3 className="font-heading text-xl font-bold flex items-center gap-2">
                                                Pagamentos PIX
                                                <Badge variant="outline" className="text-blue-500 border-blue-500/50">
                                                    Banco do Brasil
                                                </Badge>
                                            </h3>
                                            <p className="text-sm text-muted-foreground mt-1">
                                                Agende e execute pagamentos PIX diretamente pelo sistema
                                            </p>
                                        </div>
                                    </div>
                                    <Dialog open={pixDialogOpen} onOpenChange={setPixDialogOpen}>
                                        <DialogTrigger asChild>
                                            <Button className="gap-2 bg-blue-600 hover:bg-blue-700" data-testid="new-pix-btn">
                                                <QrCode className="h-4 w-4" />
                                                Novo PIX
                                            </Button>
                                        </DialogTrigger>
                                        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                                            <DialogHeader>
                                                <DialogTitle className="font-heading flex items-center gap-2">
                                                    <QrCode className="h-5 w-5 text-blue-500" />
                                                    Agendar Pagamento PIX
                                                </DialogTitle>
                                            </DialogHeader>
                                            <form onSubmit={handlePixSubmit} className="space-y-6 mt-4">
                                                {/* Recipient Info */}
                                                <div className="space-y-4">
                                                    <h4 className="font-medium text-sm text-muted-foreground uppercase tracking-wider">
                                                        Dados do Destinatário
                                                    </h4>
                                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                        <div className="space-y-2 md:col-span-2">
                                                            <Label>Nome do Destinatário *</Label>
                                                            <Input
                                                                value={pixFormData.recipient_name}
                                                                onChange={(e) => handlePixChange('recipient_name', e.target.value)}
                                                                placeholder="Nome completo ou razão social"
                                                                required
                                                                data-testid="pix-recipient-name"
                                                            />
                                                        </div>
                                                        <div className="space-y-2">
                                                            <Label>CPF/CNPJ do Destinatário *</Label>
                                                            <Input
                                                                value={pixFormData.recipient_cpf_cnpj}
                                                                onChange={(e) => handlePixChange('recipient_cpf_cnpj', e.target.value)}
                                                                placeholder="000.000.000-00"
                                                                required
                                                                data-testid="pix-recipient-cpf"
                                                            />
                                                        </div>
                                                        <div className="space-y-2">
                                                            <Label>Tipo de Chave PIX *</Label>
                                                            <Select
                                                                value={pixFormData.pix_key_type}
                                                                onValueChange={(value) => handlePixChange('pix_key_type', value)}
                                                            >
                                                                <SelectTrigger data-testid="pix-key-type-select">
                                                                    <SelectValue />
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    {pixKeyTypes.map(type => (
                                                                        <SelectItem key={type.value} value={type.value}>
                                                                            <div className="flex items-center gap-2">
                                                                                <type.icon className="h-4 w-4" />
                                                                                {type.label}
                                                                            </div>
                                                                        </SelectItem>
                                                                    ))}
                                                                </SelectContent>
                                                            </Select>
                                                        </div>
                                                        <div className="space-y-2 md:col-span-2">
                                                            <Label>Chave PIX *</Label>
                                                            <Input
                                                                value={pixFormData.pix_key}
                                                                onChange={(e) => handlePixChange('pix_key', e.target.value)}
                                                                placeholder={pixKeyTypes.find(t => t.value === pixFormData.pix_key_type)?.placeholder}
                                                                required
                                                                data-testid="pix-key-input"
                                                            />
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Payment Info */}
                                                <div className="space-y-4">
                                                    <h4 className="font-medium text-sm text-muted-foreground uppercase tracking-wider">
                                                        Dados do Pagamento
                                                    </h4>
                                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                        <div className="space-y-2">
                                                            <Label>Valor (R$) *</Label>
                                                            <Input
                                                                type="number"
                                                                step="0.01"
                                                                min="0.01"
                                                                value={pixFormData.amount}
                                                                onChange={(e) => handlePixChange('amount', e.target.value)}
                                                                required
                                                                data-testid="pix-amount-input"
                                                            />
                                                        </div>
                                                        <div className="space-y-2">
                                                            <Label>Conta de Origem *</Label>
                                                            <Select
                                                                value={pixFormData.source_account_type}
                                                                onValueChange={(value) => handlePixChange('source_account_type', value)}
                                                            >
                                                                <SelectTrigger data-testid="pix-source-account-select">
                                                                    <SelectValue />
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    {pixSourceAccounts.map(account => (
                                                                        <SelectItem key={account.value} value={account.value}>
                                                                            {account.label}
                                                                        </SelectItem>
                                                                    ))}
                                                                </SelectContent>
                                                            </Select>
                                                        </div>
                                                        <div className="space-y-2">
                                                            <Label>Data de Agendamento *</Label>
                                                            <Input
                                                                type="date"
                                                                value={pixFormData.scheduled_date}
                                                                onChange={(e) => handlePixChange('scheduled_date', e.target.value)}
                                                                min={new Date().toISOString().split('T')[0]}
                                                                required
                                                                data-testid="pix-date-input"
                                                            />
                                                        </div>
                                                        <div className="space-y-2 md:col-span-2">
                                                            <Label>Descrição *</Label>
                                                            <Input
                                                                value={pixFormData.description}
                                                                onChange={(e) => handlePixChange('description', e.target.value)}
                                                                placeholder="Descrição do pagamento (aparecerá no comprovante)"
                                                                required
                                                                data-testid="pix-description-input"
                                                            />
                                                        </div>
                                                        <div className="space-y-2 md:col-span-2">
                                                            <Label>Vincular a Despesa (opcional)</Label>
                                                            <Select
                                                                value={pixFormData.expense_id || "none"}
                                                                onValueChange={(value) => handlePixChange('expense_id', value === "none" ? "" : value)}
                                                            >
                                                                <SelectTrigger data-testid="pix-expense-select">
                                                                    <SelectValue placeholder="Selecione uma despesa pendente..." />
                                                                </SelectTrigger>
                                                                <SelectContent>
                                                                    <SelectItem value="none">Nenhuma</SelectItem>
                                                                    {expenses.map(expense => (
                                                                        <SelectItem key={expense.id} value={expense.id}>
                                                                            {expense.description} - {formatCurrency(expense.amount)}
                                                                        </SelectItem>
                                                                    ))}
                                                                </SelectContent>
                                                            </Select>
                                                            <p className="text-xs text-muted-foreground">
                                                                Ao executar o PIX, a despesa será automaticamente marcada como paga
                                                            </p>
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Integration Status */}
                                                <div className={`p-4 rounded-lg border ${
                                                    bankInfo?.integration_available 
                                                        ? 'bg-emerald-500/10 border-emerald-500/30' 
                                                        : 'bg-yellow-500/10 border-yellow-500/30'
                                                }`}>
                                                    <div className="flex items-start gap-3">
                                                        {bankInfo?.integration_available ? (
                                                            <CheckCircle className="h-5 w-5 text-emerald-500 mt-0.5" />
                                                        ) : (
                                                            <AlertCircle className="h-5 w-5 text-yellow-500 mt-0.5" />
                                                        )}
                                                        <div className="text-sm">
                                                            <p className={`font-medium ${bankInfo?.integration_available ? 'text-emerald-500' : 'text-yellow-500'}`}>
                                                                {bankInfo?.integration_available 
                                                                    ? `Integração Ativa (${bankInfo?.environment || 'homologação'})` 
                                                                    : 'Integração Simulada'}
                                                            </p>
                                                            <p className="text-muted-foreground mt-1">
                                                                {bankInfo?.integration_available 
                                                                    ? 'Conectado à API do Banco do Brasil. Os pagamentos serão processados em ambiente de ' + (bankInfo?.environment || 'homologação') + '.'
                                                                    : 'Esta é uma simulação. Para pagamentos reais, configure as credenciais da API do Banco do Brasil.'}
                                                            </p>
                                                        </div>
                                                    </div>
                                                </div>

                                                <DialogFooter>
                                                    <Button
                                                        type="button"
                                                        variant="outline"
                                                        onClick={() => setPixDialogOpen(false)}
                                                    >
                                                        Cancelar
                                                    </Button>
                                                    <Button type="submit" disabled={saving} className="bg-blue-600 hover:bg-blue-700" data-testid="pix-submit-btn">
                                                        {saving ? 'Agendando...' : 'Agendar PIX'}
                                                    </Button>
                                                </DialogFooter>
                                            </form>
                                        </DialogContent>
                                    </Dialog>
                                </div>
                            </CardContent>
                        </Card>

                        {/* PIX Summary Cards */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <Card>
                                <CardContent className="p-6">
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 rounded-xl bg-blue-500/20 flex items-center justify-center">
                                            <Calendar className="h-6 w-6 text-blue-500" />
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">PIX Agendados</p>
                                            <p className="font-heading text-2xl font-bold text-blue-500">
                                                {formatCurrency(totalPixAgendado)}
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="p-6">
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center">
                                            <CheckCircle className="h-6 w-6 text-emerald-500" />
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">PIX Executados</p>
                                            <p className="font-heading text-2xl font-bold text-emerald-500">
                                                {formatCurrency(totalPixExecutado)}
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="p-6">
                                    <div className="flex items-center gap-4">
                                        <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center">
                                            <QrCode className="h-6 w-6 text-primary" />
                                        </div>
                                        <div>
                                            <p className="text-sm text-muted-foreground">Total de PIX</p>
                                            <p className="font-heading text-2xl font-bold">
                                                {filteredPixPayments.length}
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* PIX Payments Table */}
                        <Card>
                            <CardHeader>
                                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                                    <div>
                                        <CardTitle className="font-heading">Pagamentos PIX</CardTitle>
                                        <CardDescription>Lista de pagamentos PIX agendados e executados</CardDescription>
                                    </div>
                                    <Button variant="outline" size="sm" className="gap-2" onClick={fetchPixPayments}>
                                        <RefreshCw className="h-4 w-4" />
                                        Atualizar
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent>
                                {filteredPixPayments.length === 0 ? (
                                    <div className="text-center py-12">
                                        <QrCode className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                                        <p className="text-muted-foreground">Nenhum pagamento PIX encontrado</p>
                                        <p className="text-sm text-muted-foreground mt-1">
                                            Clique em "Novo PIX" para agendar um pagamento
                                        </p>
                                    </div>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Destinatário</TableHead>
                                                    <TableHead>Chave PIX</TableHead>
                                                    <TableHead>Data</TableHead>
                                                    <TableHead>Status</TableHead>
                                                    <TableHead className="text-right">Valor</TableHead>
                                                    <TableHead className="w-32">Ações</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {filteredPixPayments.map((pix) => (
                                                    <TableRow key={pix.id} data-testid={`pix-row-${pix.id}`}>
                                                        <TableCell>
                                                            <div>
                                                                <p className="font-medium">{pix.recipient_name}</p>
                                                                <p className="text-xs text-muted-foreground">{pix.description}</p>
                                                                {pix.source_account_type && (
                                                                    <p className="text-xs text-muted-foreground">
                                                                        Origem: {pixSourceAccountLabels[pix.source_account_type] || pix.source_account_type}
                                                                    </p>
                                                                )}
                                                            </div>
                                                        </TableCell>
                                                        <TableCell>
                                                            <div className="flex items-center gap-2">
                                                                <Badge variant="outline" className="text-xs">
                                                                    {pix.pix_key_type?.toUpperCase()}
                                                                </Badge>
                                                                <code className="text-xs bg-muted px-1 py-0.5 rounded">
                                                                    {pix.pix_key?.substring(0, 15)}...
                                                                </code>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon"
                                                                    className="h-6 w-6"
                                                                    onClick={() => copyToClipboard(pix.pix_key)}
                                                                >
                                                                    <Copy className="h-3 w-3" />
                                                                </Button>
                                                            </div>
                                                        </TableCell>
                                                        <TableCell className="font-mono text-sm">
                                                            {formatDate(pix.scheduled_date)}
                                                        </TableCell>
                                                        <TableCell>
                                                            <Badge className={pixStatuses[pix.status]?.color || 'bg-gray-500/20'}>
                                                                {pixStatuses[pix.status]?.label || pix.status}
                                                            </Badge>
                                                        </TableCell>
                                                        <TableCell className="text-right font-semibold">
                                                            {formatCurrency(pix.amount)}
                                                        </TableCell>
                                                        <TableCell>
                                                            <div className="flex items-center gap-1">
                                                                {pix.status === 'agendado' && (
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="icon"
                                                                        className="text-emerald-500 hover:text-emerald-600"
                                                                        onClick={() => handleSimulatePix(pix.id)}
                                                                        title="Executar PIX (Simulação)"
                                                                        data-testid={`execute-pix-${pix.id}`}
                                                                    >
                                                                        <Send className="h-4 w-4" />
                                                                    </Button>
                                                                )}
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon"
                                                                    onClick={() => setSelectedPixPayment(pix)}
                                                                    title="Ver detalhes"
                                                                >
                                                                    <ExternalLink className="h-4 w-4" />
                                                                </Button>
                                                            </div>
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* PIX Details Modal */}
                        <Dialog open={!!selectedPixPayment} onOpenChange={() => setSelectedPixPayment(null)}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle className="flex items-center gap-2">
                                        <QrCode className="h-5 w-5 text-blue-500" />
                                        Detalhes do PIX
                                    </DialogTitle>
                                </DialogHeader>
                                {selectedPixPayment && (
                                    <div className="space-y-4">
                                        <div className="p-4 rounded-lg bg-muted/50">
                                            <div className="text-center">
                                                <p className="text-sm text-muted-foreground">Valor</p>
                                                <p className="text-3xl font-bold text-blue-500">
                                                    {formatCurrency(selectedPixPayment.amount)}
                                                </p>
                                            </div>
                                        </div>

                                        <div className="space-y-3">
                                            <div className="flex justify-between">
                                                <span className="text-sm text-muted-foreground">Status</span>
                                                <Badge className={pixStatuses[selectedPixPayment.status]?.color}>
                                                    {pixStatuses[selectedPixPayment.status]?.label}
                                                </Badge>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-sm text-muted-foreground">Destinatário</span>
                                                <span className="font-medium">{selectedPixPayment.recipient_name}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-sm text-muted-foreground">CPF/CNPJ</span>
                                                <span className="font-mono text-sm">{selectedPixPayment.recipient_cpf_cnpj}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-sm text-muted-foreground">Chave PIX</span>
                                                <span className="font-mono text-sm">{selectedPixPayment.pix_key}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-sm text-muted-foreground">Data Agendada</span>
                                                <span>{formatDate(selectedPixPayment.scheduled_date)}</span>
                                            </div>
                                            <div className="flex justify-between">
                                                <span className="text-sm text-muted-foreground">Conta de Origem</span>
                                                <span className="text-sm">
                                                    {pixSourceAccountLabels[selectedPixPayment.source_account_type] || selectedPixPayment.source_account_type || 'Conta de Doacao'}
                                                </span>
                                            </div>
                                            {selectedPixPayment.transaction_id && (
                                                <div className="flex justify-between">
                                                    <span className="text-sm text-muted-foreground">ID Transação</span>
                                                    <code className="text-xs bg-muted px-2 py-1 rounded">
                                                        {selectedPixPayment.transaction_id}
                                                    </code>
                                                </div>
                                            )}
                                        </div>

                                        {selectedPixPayment.status === 'agendado' && (
                                            <Button 
                                                className="w-full gap-2 bg-blue-600 hover:bg-blue-700"
                                                onClick={() => {
                                                    handleSimulatePix(selectedPixPayment.id);
                                                    setSelectedPixPayment(null);
                                                }}
                                            >
                                                <Send className="h-4 w-4" />
                                                Executar PIX (Simulação)
                                            </Button>
                                        )}
                                    </div>
                                )}
                            </DialogContent>
                        </Dialog>
                    </TabsContent>
                </Tabs>
            </div>
        </Layout>
    );
}
