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
import { Plus, Pencil, Trash2, FileText, Search } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const contractStatuses = [
    { value: 'rascunho', label: 'Rascunho' },
    { value: 'ativo', label: 'Ativo' },
    { value: 'concluido', label: 'Concluído' },
    { value: 'cancelado', label: 'Cancelado' }
];

const emptyForm = {
    title: '',
    description: '',
    contractor_name: '',
    contractor_cpf_cnpj: '',
    value: '',
    start_date: new Date().toISOString().split('T')[0],
    end_date: '',
    status: 'rascunho',
    notes: ''
};

export default function Contratos() {
    const [contracts, setContracts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [formData, setFormData] = useState(emptyForm);
    const [searchTerm, setSearchTerm] = useState('');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        fetchContracts();
    }, []);

    const fetchContracts = async () => {
        try {
            const response = await axios.get(`${API}/contracts`);
            setContracts(response.data);
        } catch (error) {
            toast.error('Erro ao carregar contratos');
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
                value: parseFloat(formData.value)
            };

            if (editingId) {
                await axios.put(`${API}/contracts/${editingId}`, payload);
                toast.success('Contrato atualizado!');
            } else {
                await axios.post(`${API}/contracts`, payload);
                toast.success('Contrato cadastrado!');
            }

            setDialogOpen(false);
            setEditingId(null);
            setFormData(emptyForm);
            fetchContracts();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao salvar contrato');
        } finally {
            setSaving(false);
        }
    };

    const handleEdit = (contract) => {
        setFormData({
            title: contract.title,
            description: contract.description,
            contractor_name: contract.contractor_name,
            contractor_cpf_cnpj: contract.contractor_cpf_cnpj,
            value: contract.value.toString(),
            start_date: contract.start_date,
            end_date: contract.end_date,
            status: contract.status,
            notes: contract.notes || ''
        });
        setEditingId(contract.id);
        setDialogOpen(true);
    };

    const handleDelete = async (id) => {
        if (!window.confirm('Tem certeza que deseja excluir este contrato?')) return;

        try {
            await axios.delete(`${API}/contracts/${id}`);
            toast.success('Contrato excluído!');
            fetchContracts();
        } catch (error) {
            toast.error('Erro ao excluir contrato');
        }
    };

    const filteredContracts = contracts.filter(c =>
        c.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.contractor_name.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const totalValue = filteredContracts.reduce((sum, c) => sum + c.value, 0);
    const activeContracts = filteredContracts.filter(c => c.status === 'ativo').length;

    return (
        <Layout>
            <div className="space-y-6" data-testid="contratos-page">
                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div>
                        <h1 className="font-heading text-3xl font-bold">Contratos</h1>
                        <p className="text-muted-foreground">Gerencie os contratos eleitorais</p>
                    </div>
                    <Dialog open={dialogOpen} onOpenChange={(open) => {
                        setDialogOpen(open);
                        if (!open) {
                            setEditingId(null);
                            setFormData(emptyForm);
                        }
                    }}>
                        <DialogTrigger asChild>
                            <Button className="gap-2" data-testid="add-contract-btn">
                                <Plus className="h-4 w-4" />
                                Novo Contrato
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                            <DialogHeader>
                                <DialogTitle className="font-heading">
                                    {editingId ? 'Editar Contrato' : 'Novo Contrato'}
                                </DialogTitle>
                            </DialogHeader>
                            <form onSubmit={handleSubmit} className="space-y-4 mt-4">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div className="space-y-2 md:col-span-2">
                                        <Label>Título *</Label>
                                        <Input
                                            value={formData.title}
                                            onChange={(e) => handleChange('title', e.target.value)}
                                            required
                                            data-testid="contract-title-input"
                                        />
                                    </div>
                                    <div className="space-y-2 md:col-span-2">
                                        <Label>Descrição *</Label>
                                        <Textarea
                                            value={formData.description}
                                            onChange={(e) => handleChange('description', e.target.value)}
                                            required
                                            rows={3}
                                            data-testid="contract-description-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Nome do Contratado *</Label>
                                        <Input
                                            value={formData.contractor_name}
                                            onChange={(e) => handleChange('contractor_name', e.target.value)}
                                            required
                                            data-testid="contract-contractor-name-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>CPF/CNPJ do Contratado *</Label>
                                        <Input
                                            value={formData.contractor_cpf_cnpj}
                                            onChange={(e) => handleChange('contractor_cpf_cnpj', e.target.value)}
                                            required
                                            data-testid="contract-contractor-cpf-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Valor (R$) *</Label>
                                        <Input
                                            type="number"
                                            step="0.01"
                                            min="0"
                                            value={formData.value}
                                            onChange={(e) => handleChange('value', e.target.value)}
                                            required
                                            data-testid="contract-value-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Status</Label>
                                        <Select
                                            value={formData.status}
                                            onValueChange={(value) => handleChange('status', value)}
                                        >
                                            <SelectTrigger data-testid="contract-status-select">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {contractStatuses.map(status => (
                                                    <SelectItem key={status.value} value={status.value}>
                                                        {status.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Data de Início *</Label>
                                        <Input
                                            type="date"
                                            value={formData.start_date}
                                            onChange={(e) => handleChange('start_date', e.target.value)}
                                            required
                                            data-testid="contract-start-date-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Data de Término *</Label>
                                        <Input
                                            type="date"
                                            value={formData.end_date}
                                            onChange={(e) => handleChange('end_date', e.target.value)}
                                            required
                                            data-testid="contract-end-date-input"
                                        />
                                    </div>
                                    <div className="space-y-2 md:col-span-2">
                                        <Label>Observações</Label>
                                        <Textarea
                                            value={formData.notes}
                                            onChange={(e) => handleChange('notes', e.target.value)}
                                            rows={3}
                                            data-testid="contract-notes-input"
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
                                    <Button type="submit" disabled={saving} data-testid="contract-submit-btn">
                                        {saving ? 'Salvando...' : editingId ? 'Atualizar' : 'Cadastrar'}
                                    </Button>
                                </div>
                            </form>
                        </DialogContent>
                    </Dialog>
                </div>

                {/* Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Card data-testid="contract-total-card">
                        <CardContent className="p-6">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="w-14 h-14 rounded-xl bg-primary/20 flex items-center justify-center">
                                        <FileText className="h-7 w-7 text-primary" />
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">Valor Total em Contratos</p>
                                        <p className="font-heading text-3xl font-bold">
                                            {formatCurrency(totalValue)}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    <Card data-testid="contract-active-card">
                        <CardContent className="p-6">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-4">
                                    <div className="w-14 h-14 rounded-xl bg-secondary/20 flex items-center justify-center">
                                        <FileText className="h-7 w-7 text-secondary" />
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">Contratos Ativos</p>
                                        <p className="font-heading text-3xl font-bold text-secondary">
                                            {activeContracts}
                                        </p>
                                    </div>
                                </div>
                                <Badge variant="outline" className="text-lg px-4 py-2">
                                    {filteredContracts.length} total
                                </Badge>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Search and Table */}
                <Card>
                    <CardHeader className="pb-4">
                        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                            <CardTitle className="font-heading">Lista de Contratos</CardTitle>
                            <div className="relative w-full md:w-80">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Buscar por título ou contratado..."
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    className="pl-10"
                                    data-testid="contract-search-input"
                                />
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent>
                        {loading ? (
                            <div className="text-center py-12 text-muted-foreground">Carregando...</div>
                        ) : filteredContracts.length === 0 ? (
                            <div className="text-center py-12 text-muted-foreground">
                                Nenhum contrato encontrado
                            </div>
                        ) : (
                            <div className="overflow-x-auto">
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Título</TableHead>
                                            <TableHead>Contratado</TableHead>
                                            <TableHead>Período</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead className="text-right">Valor</TableHead>
                                            <TableHead className="w-24">Ações</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {filteredContracts.map((contract) => (
                                            <TableRow key={contract.id} data-testid={`contract-row-${contract.id}`}>
                                                <TableCell className="font-medium">
                                                    {contract.title}
                                                </TableCell>
                                                <TableCell className="text-muted-foreground">
                                                    {contract.contractor_name}
                                                </TableCell>
                                                <TableCell className="font-mono text-sm">
                                                    {formatDate(contract.start_date)} - {formatDate(contract.end_date)}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge className={statusColors[contract.status]}>
                                                        {statusLabels[contract.status]}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-right font-mono font-medium">
                                                    {formatCurrency(contract.value)}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex gap-1">
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => handleEdit(contract)}
                                                            data-testid={`edit-contract-${contract.id}`}
                                                        >
                                                            <Pencil className="h-4 w-4" />
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => handleDelete(contract.id)}
                                                            className="text-destructive hover:text-destructive"
                                                            data-testid={`delete-contract-${contract.id}`}
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
