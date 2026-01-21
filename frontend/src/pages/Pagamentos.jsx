import { useState, useEffect } from 'react';
import axios from 'axios';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { formatCurrency, formatDate, statusLabels, statusColors } from '../lib/utils';
import { Plus, Pencil, Trash2, CreditCard, Search, Clock, CheckCircle } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const paymentStatuses = [
    { value: 'pendente', label: 'Pendente' },
    { value: 'pago', label: 'Pago' },
    { value: 'cancelado', label: 'Cancelado' }
];

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

export default function Pagamentos() {
    const [payments, setPayments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [formData, setFormData] = useState(emptyForm);
    const [searchTerm, setSearchTerm] = useState('');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        fetchPayments();
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

    const handleChange = (field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
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

    const filteredPayments = payments.filter(p =>
        p.description.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const totalPayments = filteredPayments.reduce((sum, p) => sum + p.amount, 0);
    const pendingPayments = filteredPayments.filter(p => p.status === 'pendente');
    const pendingTotal = pendingPayments.reduce((sum, p) => sum + p.amount, 0);

    return (
        <Layout>
            <div className="space-y-6" data-testid="pagamentos-page">
                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div>
                        <h1 className="font-heading text-3xl font-bold">Pagamentos</h1>
                        <p className="text-muted-foreground">Controle os pagamentos da campanha</p>
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

                {/* Search and Table */}
                <Card>
                    <CardHeader className="pb-4">
                        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                            <CardTitle className="font-heading">Lista de Pagamentos</CardTitle>
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
                                                <TableCell className="text-right font-mono font-medium">
                                                    {formatCurrency(payment.amount)}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex gap-1">
                                                        {payment.status === 'pendente' && (
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                onClick={() => handleMarkAsPaid(payment)}
                                                                className="text-secondary hover:text-secondary"
                                                                title="Marcar como pago"
                                                                data-testid={`mark-paid-${payment.id}`}
                                                            >
                                                                <CheckCircle className="h-4 w-4" />
                                                            </Button>
                                                        )}
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => handleEdit(payment)}
                                                            data-testid={`edit-payment-${payment.id}`}
                                                        >
                                                            <Pencil className="h-4 w-4" />
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => handleDelete(payment.id)}
                                                            className="text-destructive hover:text-destructive"
                                                            data-testid={`delete-payment-${payment.id}`}
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
            </div>
        </Layout>
    );
}
