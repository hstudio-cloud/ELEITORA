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
import { formatCurrency, formatDate, categoryLabels } from '../lib/utils';
import { Plus, Pencil, Trash2, TrendingDown, Search, Filter, X, Upload, FileText, CheckCircle, Clock, Paperclip } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const expenseCategories = [
    { value: 'publicidade', label: 'Publicidade' },
    { value: 'material_grafico', label: 'Material Gráfico' },
    { value: 'servicos_terceiros', label: 'Serviços de Terceiros' },
    { value: 'transporte', label: 'Transporte' },
    { value: 'alimentacao', label: 'Alimentação' },
    { value: 'pessoal', label: 'Pessoal' },
    { value: 'eventos', label: 'Eventos' },
    { value: 'outros', label: 'Outros' }
];

const emptyForm = {
    description: '',
    amount: '',
    category: 'publicidade',
    supplier_name: '',
    supplier_cpf_cnpj: '',
    date: new Date().toISOString().split('T')[0],
    invoice_number: '',
    notes: ''
};

export default function Despesas() {
    const [expenses, setExpenses] = useState([]);
    const [loading, setLoading] = useState(true);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [formData, setFormData] = useState(emptyForm);
    const [searchTerm, setSearchTerm] = useState('');
    const [saving, setSaving] = useState(false);
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');

    useEffect(() => {
        fetchExpenses();
    }, []);

    const fetchExpenses = async () => {
        try {
            const response = await axios.get(`${API}/expenses`);
            setExpenses(response.data);
        } catch (error) {
            toast.error('Erro ao carregar despesas');
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
                amount: parseFloat(formData.amount)
            };

            if (editingId) {
                await axios.put(`${API}/expenses/${editingId}`, payload);
                toast.success('Despesa atualizada!');
            } else {
                await axios.post(`${API}/expenses`, payload);
                toast.success('Despesa cadastrada!');
            }

            setDialogOpen(false);
            setEditingId(null);
            setFormData(emptyForm);
            fetchExpenses();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao salvar despesa');
        } finally {
            setSaving(false);
        }
    };

    const handleEdit = (expense) => {
        setFormData({
            description: expense.description,
            amount: expense.amount.toString(),
            category: expense.category,
            supplier_name: expense.supplier_name || '',
            supplier_cpf_cnpj: expense.supplier_cpf_cnpj || '',
            date: expense.date,
            invoice_number: expense.invoice_number || '',
            notes: expense.notes || ''
        });
        setEditingId(expense.id);
        setDialogOpen(true);
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Tem certeza que deseja excluir esta despesa?')) return;

        try {
            await axios.delete(`${API}/expenses/${id}`);
            toast.success('Despesa excluída!');
            fetchExpenses();
        } catch (error) {
            toast.error('Erro ao excluir despesa');
        }
    };

    const filteredExpenses = expenses.filter(e => {
        const matchesSearch = e.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
            e.supplier_name?.toLowerCase().includes(searchTerm.toLowerCase());
        
        const matchesDateRange = (!startDate || e.date >= startDate) && 
            (!endDate || e.date <= endDate);
        
        return matchesSearch && matchesDateRange;
    });

    const clearFilters = () => {
        setStartDate('');
        setEndDate('');
        setSearchTerm('');
    };

    const totalExpenses = filteredExpenses.reduce((sum, e) => sum + e.amount, 0);

    return (
        <Layout>
            <div className="space-y-6" data-testid="despesas-page">
                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div>
                        <h1 className="font-heading text-3xl font-bold">Despesas</h1>
                        <p className="text-muted-foreground">Gerencie as despesas da campanha</p>
                    </div>
                    <Dialog open={dialogOpen} onOpenChange={(open) => {
                        setDialogOpen(open);
                        if (!open) {
                            setEditingId(null);
                            setFormData(emptyForm);
                        }
                    }}>
                        <DialogTrigger asChild>
                            <Button className="gap-2" data-testid="add-expense-btn">
                                <Plus className="h-4 w-4" />
                                Nova Despesa
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                            <DialogHeader>
                                <DialogTitle className="font-heading">
                                    {editingId ? 'Editar Despesa' : 'Nova Despesa'}
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
                                            data-testid="expense-description-input"
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
                                            data-testid="expense-amount-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Categoria *</Label>
                                        <Select
                                            value={formData.category}
                                            onValueChange={(value) => handleChange('category', value)}
                                        >
                                            <SelectTrigger data-testid="expense-category-select">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {expenseCategories.map(cat => (
                                                    <SelectItem key={cat.value} value={cat.value}>
                                                        {cat.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Nome do Fornecedor</Label>
                                        <Input
                                            value={formData.supplier_name}
                                            onChange={(e) => handleChange('supplier_name', e.target.value)}
                                            data-testid="expense-supplier-name-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>CPF/CNPJ do Fornecedor</Label>
                                        <Input
                                            value={formData.supplier_cpf_cnpj}
                                            onChange={(e) => handleChange('supplier_cpf_cnpj', e.target.value)}
                                            data-testid="expense-supplier-cpf-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Data *</Label>
                                        <Input
                                            type="date"
                                            value={formData.date}
                                            onChange={(e) => handleChange('date', e.target.value)}
                                            required
                                            data-testid="expense-date-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Número da Nota Fiscal</Label>
                                        <Input
                                            value={formData.invoice_number}
                                            onChange={(e) => handleChange('invoice_number', e.target.value)}
                                            data-testid="expense-invoice-input"
                                        />
                                    </div>
                                    <div className="space-y-2 md:col-span-2">
                                        <Label>Observações</Label>
                                        <Textarea
                                            value={formData.notes}
                                            onChange={(e) => handleChange('notes', e.target.value)}
                                            rows={3}
                                            data-testid="expense-notes-input"
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
                                    <Button type="submit" disabled={saving} data-testid="expense-submit-btn">
                                        {saving ? 'Salvando...' : editingId ? 'Atualizar' : 'Cadastrar'}
                                    </Button>
                                </div>
                            </form>
                        </DialogContent>
                    </Dialog>
                </div>

                {/* Summary Card */}
                <Card data-testid="expense-summary-card">
                    <CardContent className="p-6">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className="w-14 h-14 rounded-xl bg-destructive/20 flex items-center justify-center">
                                    <TrendingDown className="h-7 w-7 text-destructive" />
                                </div>
                                <div>
                                    <p className="text-sm text-muted-foreground">Total de Despesas</p>
                                    <p className="font-heading text-3xl font-bold text-destructive">
                                        {formatCurrency(totalExpenses)}
                                    </p>
                                </div>
                            </div>
                            <Badge variant="destructive" className="text-lg px-4 py-2">
                                {filteredExpenses.length} registros
                            </Badge>
                        </div>
                    </CardContent>
                </Card>

                {/* Search and Table */}
                <Card>
                    <CardHeader className="pb-4">
                        <div className="flex flex-col gap-4">
                            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                                <CardTitle className="font-heading">Lista de Despesas</CardTitle>
                                <div className="relative w-full md:w-80">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                    <Input
                                        placeholder="Buscar por descrição ou fornecedor..."
                                        value={searchTerm}
                                        onChange={(e) => setSearchTerm(e.target.value)}
                                        className="pl-10"
                                        data-testid="expense-search-input"
                                    />
                                </div>
                            </div>
                            {/* Date Filters */}
                            <div className="flex flex-wrap items-center gap-3">
                                <div className="flex items-center gap-2">
                                    <Filter className="h-4 w-4 text-muted-foreground" />
                                    <span className="text-sm text-muted-foreground">Período:</span>
                                </div>
                                <Input
                                    type="date"
                                    value={startDate}
                                    onChange={(e) => setStartDate(e.target.value)}
                                    className="w-40"
                                    placeholder="Data início"
                                    data-testid="expense-start-date-filter"
                                />
                                <span className="text-muted-foreground">até</span>
                                <Input
                                    type="date"
                                    value={endDate}
                                    onChange={(e) => setEndDate(e.target.value)}
                                    className="w-40"
                                    placeholder="Data fim"
                                    data-testid="expense-end-date-filter"
                                />
                                {(startDate || endDate || searchTerm) && (
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={clearFilters}
                                        className="gap-1 text-muted-foreground"
                                        data-testid="clear-filters-btn"
                                    >
                                        <X className="h-4 w-4" />
                                        Limpar filtros
                                    </Button>
                                )}
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent>
                        {loading ? (
                            <div className="text-center py-12 text-muted-foreground">Carregando...</div>
                        ) : filteredExpenses.length === 0 ? (
                            <div className="text-center py-12 text-muted-foreground">
                                Nenhuma despesa encontrada
                            </div>
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
                                            <TableHead className="w-24">Ações</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {filteredExpenses.map((expense) => (
                                            <TableRow key={expense.id} data-testid={`expense-row-${expense.id}`}>
                                                <TableCell className="font-mono text-sm">
                                                    {formatDate(expense.date)}
                                                </TableCell>
                                                <TableCell className="font-medium">
                                                    {expense.description}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant="outline">
                                                        {categoryLabels[expense.category] || expense.category}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-muted-foreground">
                                                    {expense.supplier_name || '-'}
                                                </TableCell>
                                                <TableCell className="text-right font-mono font-medium text-destructive">
                                                    {formatCurrency(expense.amount)}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex gap-1">
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => handleEdit(expense)}
                                                            data-testid={`edit-expense-${expense.id}`}
                                                        >
                                                            <Pencil className="h-4 w-4" />
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => handleDelete(expense.id)}
                                                            className="text-destructive hover:text-destructive"
                                                            data-testid={`delete-expense-${expense.id}`}
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
