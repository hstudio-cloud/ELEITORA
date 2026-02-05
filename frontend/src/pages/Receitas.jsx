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
import { Plus, Pencil, Trash2, TrendingUp, Search, Filter, X, Upload, Paperclip } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const revenueCategories = [
    { value: 'doacao_pf', label: 'Doação Pessoa Física' },
    { value: 'doacao_pj', label: 'Doação Pessoa Jurídica' },
    { value: 'recursos_proprios', label: 'Recursos Próprios' },
    { value: 'fundo_eleitoral', label: 'Fundo Eleitoral' },
    { value: 'fundo_partidario', label: 'Fundo Partidário' },
    { value: 'outros', label: 'Outros' }
];

const emptyForm = {
    description: '',
    amount: '',
    category: 'doacao_pf',
    donor_name: '',
    donor_cpf_cnpj: '',
    date: new Date().toISOString().split('T')[0],
    receipt_number: '',
    notes: ''
};

export default function Receitas() {
    const [revenues, setRevenues] = useState([]);
    const [loading, setLoading] = useState(true);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [formData, setFormData] = useState(emptyForm);
    const [searchTerm, setSearchTerm] = useState('');
    const [saving, setSaving] = useState(false);
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');

    useEffect(() => {
        fetchRevenues();
    }, []);

    const fetchRevenues = async () => {
        try {
            const response = await axios.get(`${API}/revenues`);
            setRevenues(response.data);
        } catch (error) {
            toast.error('Erro ao carregar receitas');
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
                await axios.put(`${API}/revenues/${editingId}`, payload);
                toast.success('Receita atualizada!');
            } else {
                await axios.post(`${API}/revenues`, payload);
                toast.success('Receita cadastrada!');
            }

            setDialogOpen(false);
            setEditingId(null);
            setFormData(emptyForm);
            fetchRevenues();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao salvar receita');
        } finally {
            setSaving(false);
        }
    };

    const handleEdit = (revenue) => {
        setFormData({
            description: revenue.description,
            amount: revenue.amount.toString(),
            category: revenue.category,
            donor_name: revenue.donor_name || '',
            donor_cpf_cnpj: revenue.donor_cpf_cnpj || '',
            date: revenue.date,
            receipt_number: revenue.receipt_number || '',
            notes: revenue.notes || ''
        });
        setEditingId(revenue.id);
        setDialogOpen(true);
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Tem certeza que deseja excluir esta receita?')) return;

        try {
            await axios.delete(`${API}/revenues/${id}`);
            toast.success('Receita excluída!');
            fetchRevenues();
        } catch (error) {
            toast.error('Erro ao excluir receita');
        }
    };

    const filteredRevenues = revenues.filter(r => {
        const matchesSearch = r.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
            r.donor_name?.toLowerCase().includes(searchTerm.toLowerCase());
        
        const matchesDateRange = (!startDate || r.date >= startDate) && 
            (!endDate || r.date <= endDate);
        
        return matchesSearch && matchesDateRange;
    });

    const clearFilters = () => {
        setStartDate('');
        setEndDate('');
        setSearchTerm('');
    };

    const totalRevenues = filteredRevenues.reduce((sum, r) => sum + r.amount, 0);

    return (
        <Layout>
            <div className="space-y-6" data-testid="receitas-page">
                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div>
                        <h1 className="font-heading text-3xl font-bold">Receitas</h1>
                        <p className="text-muted-foreground">Gerencie as receitas da campanha</p>
                    </div>
                    <Dialog open={dialogOpen} onOpenChange={(open) => {
                        setDialogOpen(open);
                        if (!open) {
                            setEditingId(null);
                            setFormData(emptyForm);
                        }
                    }}>
                        <DialogTrigger asChild>
                            <Button className="gap-2" data-testid="add-revenue-btn">
                                <Plus className="h-4 w-4" />
                                Nova Receita
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                            <DialogHeader>
                                <DialogTitle className="font-heading">
                                    {editingId ? 'Editar Receita' : 'Nova Receita'}
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
                                            data-testid="revenue-description-input"
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
                                            data-testid="revenue-amount-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Categoria *</Label>
                                        <Select
                                            value={formData.category}
                                            onValueChange={(value) => handleChange('category', value)}
                                        >
                                            <SelectTrigger data-testid="revenue-category-select">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {revenueCategories.map(cat => (
                                                    <SelectItem key={cat.value} value={cat.value}>
                                                        {cat.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Nome do Doador</Label>
                                        <Input
                                            value={formData.donor_name}
                                            onChange={(e) => handleChange('donor_name', e.target.value)}
                                            data-testid="revenue-donor-name-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>CPF/CNPJ do Doador</Label>
                                        <Input
                                            value={formData.donor_cpf_cnpj}
                                            onChange={(e) => handleChange('donor_cpf_cnpj', e.target.value)}
                                            data-testid="revenue-donor-cpf-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Data *</Label>
                                        <Input
                                            type="date"
                                            value={formData.date}
                                            onChange={(e) => handleChange('date', e.target.value)}
                                            required
                                            data-testid="revenue-date-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Número do Recibo</Label>
                                        <Input
                                            value={formData.receipt_number}
                                            onChange={(e) => handleChange('receipt_number', e.target.value)}
                                            data-testid="revenue-receipt-input"
                                        />
                                    </div>
                                    <div className="space-y-2 md:col-span-2">
                                        <Label>Observações</Label>
                                        <Textarea
                                            value={formData.notes}
                                            onChange={(e) => handleChange('notes', e.target.value)}
                                            rows={3}
                                            data-testid="revenue-notes-input"
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
                                    <Button type="submit" disabled={saving} data-testid="revenue-submit-btn">
                                        {saving ? 'Salvando...' : editingId ? 'Atualizar' : 'Cadastrar'}
                                    </Button>
                                </div>
                            </form>
                        </DialogContent>
                    </Dialog>
                </div>

                {/* Summary Card */}
                <Card data-testid="revenue-summary-card">
                    <CardContent className="p-6">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className="w-14 h-14 rounded-xl bg-secondary/20 flex items-center justify-center">
                                    <TrendingUp className="h-7 w-7 text-secondary" />
                                </div>
                                <div>
                                    <p className="text-sm text-muted-foreground">Total de Receitas</p>
                                    <p className="font-heading text-3xl font-bold text-secondary">
                                        {formatCurrency(totalRevenues)}
                                    </p>
                                </div>
                            </div>
                            <Badge variant="secondary" className="text-lg px-4 py-2">
                                {filteredRevenues.length} registros
                            </Badge>
                        </div>
                    </CardContent>
                </Card>

                {/* Search and Table */}
                <Card>
                    <CardHeader className="pb-4">
                        <div className="flex flex-col gap-4">
                            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                                <CardTitle className="font-heading">Lista de Receitas</CardTitle>
                                <div className="relative w-full md:w-80">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                    <Input
                                        placeholder="Buscar por descrição ou doador..."
                                        value={searchTerm}
                                        onChange={(e) => setSearchTerm(e.target.value)}
                                        className="pl-10"
                                        data-testid="revenue-search-input"
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
                                    data-testid="revenue-start-date-filter"
                                />
                                <span className="text-muted-foreground">até</span>
                                <Input
                                    type="date"
                                    value={endDate}
                                    onChange={(e) => setEndDate(e.target.value)}
                                    className="w-40"
                                    placeholder="Data fim"
                                    data-testid="revenue-end-date-filter"
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
                        ) : filteredRevenues.length === 0 ? (
                            <div className="text-center py-12 text-muted-foreground">
                                Nenhuma receita encontrada
                            </div>
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
                                            <TableHead className="w-24">Ações</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {filteredRevenues.map((revenue) => (
                                            <TableRow key={revenue.id} data-testid={`revenue-row-${revenue.id}`}>
                                                <TableCell className="font-mono text-sm">
                                                    {formatDate(revenue.date)}
                                                </TableCell>
                                                <TableCell className="font-medium">
                                                    {revenue.description}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant="outline">
                                                        {categoryLabels[revenue.category] || revenue.category}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-muted-foreground">
                                                    {revenue.donor_name || '-'}
                                                </TableCell>
                                                <TableCell className="text-right font-mono font-medium text-secondary">
                                                    {formatCurrency(revenue.amount)}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex gap-1">
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => handleEdit(revenue)}
                                                            data-testid={`edit-revenue-${revenue.id}`}
                                                        >
                                                            <Pencil className="h-4 w-4" />
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => handleDelete(revenue.id)}
                                                            className="text-destructive hover:text-destructive"
                                                            data-testid={`delete-revenue-${revenue.id}`}
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
