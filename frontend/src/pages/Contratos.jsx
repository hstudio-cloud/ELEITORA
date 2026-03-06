import { useState, useEffect } from 'react';
import axios from 'axios';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription } from '../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import { formatCurrency, formatDate, statusLabels, statusColors } from '../lib/utils';
import { 
    Plus, Pencil, Trash2, FileText, Search, Eye, Send, 
    CheckCircle, Clock, FileSignature, Download, Upload, DollarSign,
    AlertTriangle, FileCheck, Loader2
} from 'lucide-react';
import { Checkbox } from '../components/ui/checkbox';
import { Progress } from '../components/ui/progress';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const contractTemplates = [
    { value: 'veiculo_com_motorista', label: 'Veiculo com Motorista', description: 'Carro de som, paredao e deslocamento com condutor' },
    { value: 'veiculo_sem_motorista', label: 'Veiculo sem Motorista', description: 'Veiculo sem condutor' },
    { value: 'imovel_comite', label: 'Imovel para Comite', description: 'Sede, comite e escritorio de campanha' },
    { value: 'imovel_evento', label: 'Imovel para Evento', description: 'Espaco para reuniao e ato eleitoral' },
    { value: 'servico_grafico', label: 'Servicos Graficos', description: 'Impressos e materiais de campanha' },
    { value: 'servico_publicidade', label: 'Servicos de Publicidade', description: 'Planejamento e veiculacao de campanha' },
    { value: 'servico_pesquisa', label: 'Servicos de Pesquisa', description: 'Pesquisa eleitoral e diagnostico' },
    { value: 'servico_juridico', label: 'Servicos Juridicos', description: 'Assessoria e consultoria juridica' },
    { value: 'servico_contabil', label: 'Servicos Contabeis', description: 'Contabilidade eleitoral e SPCE' },
    { value: 'servico_ti', label: 'Servicos de TI', description: 'Suporte tecnico, sistemas e dados' },
    { value: 'producao_audiovisual', label: 'Producao Audiovisual', description: 'Videos, jingles e conteudo' },
    { value: 'impulsionamento', label: 'Impulsionamento de Conteudo', description: 'Midias digitais e plataformas' },
    { value: 'outros', label: 'Outros Contratos', description: 'Demais servicos/locacoes permitidos' },
    { value: 'bem_movel', label: 'Bem Movel (Legado)', description: 'Tipo legado para contratos antigos' },
    { value: 'imovel', label: 'Imovel (Legado)', description: 'Tipo legado mapeado para comite' },
    { value: 'espaco_evento', label: 'Espaco Evento (Legado)', description: 'Tipo legado mapeado para evento' }
];

const contractStatuses = [
    { value: 'rascunho', label: 'Rascunho' },
    { value: 'aguardando_assinatura', label: 'Aguardando Assinatura' },
    { value: 'assinado_locador', label: 'Assinado pelo Locador' },
    { value: 'assinado_locatario', label: 'Assinado pelo Locatário' },
    { value: 'ativo', label: 'Ativo' },
    { value: 'concluido', label: 'Concluído' },
    { value: 'cancelado', label: 'Cancelado' }
];

const statusColorsExtended = {
    rascunho: 'bg-muted text-muted-foreground',
    aguardando_assinatura: 'bg-accent/20 text-accent',
    assinado_locador: 'bg-blue-500/20 text-blue-400',
    assinado_locatario: 'bg-blue-500/20 text-blue-400',
    ativo: 'bg-secondary/20 text-secondary',
    concluido: 'bg-primary/20 text-primary',
    cancelado: 'bg-destructive/20 text-destructive'
};

const pendingSignatureStatuses = ['aguardando_assinatura', 'assinado_locador', 'assinado_locatario'];

const emptyForm = {
    title: '',
    description: '',
    contractor_name: '',
    contractor_cpf_cnpj: '',
    value: '',
    start_date: new Date().toISOString().split('T')[0],
    end_date: '',
    status: 'rascunho',
    notes: '',
    template_type: '',
    contador_professional_id: '',
    // Payment installments
    num_parcelas: 1,
    gerar_despesas: true,
    parcelas_config: [],
    // Locador fields
    locador_nome: '',
    locador_nacionalidade: 'Brasileiro(a)',
    locador_estado_civil: '',
    locador_profissao: '',
    locador_endereco: '',
    locador_numero: '',
    locador_cep: '',
    locador_bairro: '',
    locador_cidade: '',
    locador_estado: '',
    locador_rg: '',
    locador_cpf: '',
    locador_email: '',
    // Object
    objeto_descricao: '',
    // Vehicle fields
    veiculo_marca: '',
    veiculo_modelo: '',
    veiculo_ano: '',
    veiculo_placa: '',
    veiculo_renavam: '',
    // Property fields
    imovel_descricao: '',
    imovel_registro: '',
    // Driver fields
    motorista_nome: '',
    motorista_cnh: '',
    // Trailer fields
    reboque_descricao: '',
    reboque_placa: '',
    reboque_renavam: '',
    // Event fields
    evento_horario_inicio: '',
    evento_horario_fim: ''
};

export default function Contratos() {
    const [contracts, setContracts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [previewDialogOpen, setPreviewDialogOpen] = useState(false);
    const [signatureDialogOpen, setSignatureDialogOpen] = useState(false);
    const [editingId, setEditingId] = useState(null);
    const [formData, setFormData] = useState(emptyForm);
    const [searchTerm, setSearchTerm] = useState('');
    const [saving, setSaving] = useState(false);
    const [previewHtml, setPreviewHtml] = useState('');
    const [selectedContract, setSelectedContract] = useState(null);
    const [signatureEmail, setSignatureEmail] = useState('');
    const [contractExpenses, setContractExpenses] = useState([]);
    const [expensesDialogOpen, setExpensesDialogOpen] = useState(false);
    const [attachmentsDialogOpen, setAttachmentsDialogOpen] = useState(false);
    const [selectedContractAttachments, setSelectedContractAttachments] = useState(null);
    const [uploadingAttachmentKey, setUploadingAttachmentKey] = useState(null);
    const [contadores, setContadores] = useState([]);

    useEffect(() => {
        fetchContracts();
        fetchContadores();
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
        setFormData(prev => {
            const updated = { ...prev, [field]: value };
            
            // Auto-sync locador fields with contractor fields
            if (field === 'locador_nome') {
                updated.contractor_name = value;
            }
            if (field === 'locador_cpf') {
                updated.contractor_cpf_cnpj = value;
            }
            
            return updated;
        });
    };

    const handleTemplateChange = (templateType) => {
        const template = contractTemplates.find(t => t.value === templateType);
        setFormData(prev => ({
            ...prev,
            template_type: templateType,
            contador_professional_id: templateType === 'servico_contabil' ? prev.contador_professional_id : '',
            title: template ? `Contrato de ${template.label}` : prev.title
        }));
    };

    const handleSelectContador = (contadorId) => {
        const contador = contadores.find(c => c.id === contadorId);
        if (!contador) {
            handleChange('contador_professional_id', '');
            return;
        }

        setFormData(prev => ({
            ...prev,
            contador_professional_id: contador.id,
            contractor_name: contador.name || prev.contractor_name,
            contractor_cpf_cnpj: contador.cpf || prev.contractor_cpf_cnpj,
            locador_nome: contador.name || prev.locador_nome,
            locador_cpf: contador.cpf || prev.locador_cpf,
            locador_email: contador.email || prev.locador_email,
            locador_profissao: 'Contador(a)'
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);

        try {
            const payload = {
                ...formData,
                value: parseFloat(formData.value),
                num_parcelas: parseInt(formData.num_parcelas) || 1,
                gerar_despesas: formData.gerar_despesas !== false // Default to true
            };

            if (editingId) {
                await axios.put(`${API}/contracts/${editingId}`, payload);
                toast.success('Contrato atualizado!');
            } else {
                await axios.post(`${API}/contracts`, payload);
                toast.success('Contrato criado! Despesas geradas automaticamente.');
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

    const fetchContractExpenses = async (contractId) => {
        try {
            const response = await axios.get(`${API}/contracts/${contractId}/expenses`);
            setContractExpenses(response.data);
            setExpensesDialogOpen(true);
        } catch (error) {
            toast.error('Erro ao carregar despesas do contrato');
        }
    };

    const fetchContractAttachments = async (contractId) => {
        try {
            const response = await axios.get(`${API}/contracts/${contractId}/required-attachments`);
            setSelectedContractAttachments(response.data);
            setAttachmentsDialogOpen(true);
        } catch (error) {
            toast.error('Erro ao carregar anexos do contrato');
        }
    };

    const handleUploadSpecificAttachment = async (contractId, attachmentKey, file) => {
        if (!file) return;
        
        const allowedTypes = ['image/jpeg', 'image/png', 'application/pdf'];
        if (!allowedTypes.includes(file.type)) {
            toast.error('Tipo de arquivo não permitido. Use: JPEG, PNG ou PDF');
            return;
        }

        setUploadingAttachmentKey(attachmentKey);
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await axios.post(
                `${API}/contracts/${contractId}/attachments/${attachmentKey}`, 
                formData, 
                { headers: { 'Content-Type': 'multipart/form-data' } }
            );
            toast.success(response.data.message);
            // Refresh attachments
            fetchContractAttachments(contractId);
            fetchContracts();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao anexar documento');
        } finally {
            setUploadingAttachmentKey(null);
        }
    };

    const handleEdit = (contract) => {
        setFormData({
            title: contract.title || '',
            description: contract.description || '',
            contractor_name: contract.contractor_name || '',
            contractor_cpf_cnpj: contract.contractor_cpf_cnpj || '',
            value: contract.value?.toString() || '',
            start_date: contract.start_date || '',
            end_date: contract.end_date || '',
            status: contract.status || 'rascunho',
            notes: contract.notes || '',
            template_type: contract.template_type || '',
            contador_professional_id: contract.contador_professional_id || '',
            locador_nome: contract.locador_nome || '',
            locador_nacionalidade: contract.locador_nacionalidade || 'Brasileiro(a)',
            locador_estado_civil: contract.locador_estado_civil || '',
            locador_profissao: contract.locador_profissao || '',
            locador_endereco: contract.locador_endereco || '',
            locador_numero: contract.locador_numero || '',
            locador_cep: contract.locador_cep || '',
            locador_bairro: contract.locador_bairro || '',
            locador_cidade: contract.locador_cidade || '',
            locador_estado: contract.locador_estado || '',
            locador_rg: contract.locador_rg || '',
            locador_cpf: contract.locador_cpf || '',
            locador_email: contract.locador_email || '',
            objeto_descricao: contract.objeto_descricao || '',
            veiculo_marca: contract.veiculo_marca || '',
            veiculo_modelo: contract.veiculo_modelo || '',
            veiculo_ano: contract.veiculo_ano || '',
            veiculo_placa: contract.veiculo_placa || '',
            veiculo_renavam: contract.veiculo_renavam || '',
            imovel_descricao: contract.imovel_descricao || '',
            imovel_registro: contract.imovel_registro || '',
            motorista_nome: contract.motorista_nome || '',
            motorista_cnh: contract.motorista_cnh || '',
            reboque_descricao: contract.reboque_descricao || '',
            reboque_placa: contract.reboque_placa || '',
            reboque_renavam: contract.reboque_renavam || '',
            evento_horario_inicio: contract.evento_horario_inicio || '',
            evento_horario_fim: contract.evento_horario_fim || ''
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

    const handlePreview = async (contract) => {
        try {
            const response = await axios.get(`${API}/contracts/${contract.id}/html`);
            setPreviewHtml(response.data.html);
            setSelectedContract(contract);
            setPreviewDialogOpen(true);
        } catch (error) {
            toast.error('Erro ao carregar preview');
        }
    };

    const handleRequestSignature = async () => {
        if (!selectedContract) {
            return;
        }

        try {
            const response = await axios.post(`${API}/contracts/${selectedContract.id}/request-signature`, {
                contract_id: selectedContract.id,
                locador_email: signatureEmail
            });
            
            toast.success('Fluxo de assinatura externa iniciado!');
            window.open(`${API}/contracts/${selectedContract.id}/pdf`, '_blank');
            window.open(response?.data?.govbr_url || 'https://assinador.iti.br/', '_blank');
            toast.info('PDF do contrato baixado e Gov.br aberto para assinatura digital.');
            
            setSignatureDialogOpen(false);
            setSignatureEmail('');
            fetchContracts();
        } catch (error) {
            toast.error('Erro ao solicitar assinatura');
        }
    };

    const handleUploadSignedContract = async (contract) => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.pdf,.jpg,.jpeg,.png';
        input.onchange = async (event) => {
            const file = event.target.files?.[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            try {
                await axios.post(`${API}/contracts/${contract.id}/upload-signed-document`, formData, {
                    headers: { 'Content-Type': 'multipart/form-data' }
                });
                toast.success('Contrato assinado anexado! Status atualizado para ativo.');
                fetchContracts();
            } catch (error) {
                toast.error(error.response?.data?.detail || 'Erro ao anexar contrato assinado');
            }
        };
        input.click();
    };

    const fetchContadores = async () => {
        try {
            const response = await axios.get(`${API}/professionals`, { params: { type: 'contador' } });
            setContadores(response.data || []);
        } catch (error) {
            setContadores([]);
        }
    };

    const checkSignatureReminders = (contractsToCheck) => {
        const today = new Date().toISOString().split('T')[0];
        const now = Date.now();
        const intervalMs = 30 * 60 * 1000;

        contractsToCheck.forEach((contract) => {
            const needsReminder =
                contract.start_date === today &&
                pendingSignatureStatuses.includes(contract.status) &&
                !contract.signed_document_attachment_id;

            if (!needsReminder) return;

            const reminderKey = `eleitora_signature_reminder_${contract.id}`;
            const lastReminder = Number(localStorage.getItem(reminderKey) || '0');
            if (now - lastReminder < intervalMs) return;

            toast.warning(`Lembrete: anexe o contrato assinado (${contract.title}) para concluir a assinatura.`, {
                duration: 8000
            });
            localStorage.setItem(reminderKey, String(now));
        });
    };

    useEffect(() => {
        if (!contracts.length) return;
        checkSignatureReminders(contracts);

        const intervalId = window.setInterval(() => {
            checkSignatureReminders(contracts);
        }, 30 * 60 * 1000);

        return () => window.clearInterval(intervalId);
    }, [contracts]);

    const filteredContracts = contracts.filter(c =>
        c.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.contractor_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.locador_nome?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const totalValue = filteredContracts.reduce((sum, c) => sum + (c.value || 0), 0);
    const activeContracts = filteredContracts.filter(c => c.status === 'ativo').length;
    const pendingSignatures = filteredContracts.filter(c => pendingSignatureStatuses.includes(c.status)).length;

    const renderTemplateFields = () => {
        const type = formData.template_type;
        
        if (!type) return null;

        return (
            <>
                {type === 'servico_contabil' && (
                    <div className="space-y-2 md:col-span-2">
                        <Label>Selecionar Contador Cadastrado</Label>
                        <Select
                            value={formData.contador_professional_id || ''}
                            onValueChange={handleSelectContador}
                        >
                            <SelectTrigger data-testid="contract-contador-select">
                                <SelectValue placeholder="Escolha um contador da plataforma" />
                            </SelectTrigger>
                            <SelectContent>
                                {contadores.map((contador) => (
                                    <SelectItem key={contador.id} value={contador.id}>
                                        {contador.name} {contador.crc ? `- CRC ${contador.crc}/${contador.crc_state || ''}` : ''}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">
                            Ao selecionar, os dados do contador e documentos de cadastro/CRC serão anexados automaticamente ao contrato.
                        </p>
                    </div>
                )}

                {/* Common object description */}
                <div className="space-y-2 md:col-span-2">
                    <Label>Descrição do Objeto *</Label>
                    <Textarea
                        value={formData.objeto_descricao}
                        onChange={(e) => handleChange('objeto_descricao', e.target.value)}
                        placeholder="Descreva o bem/serviço a ser locado"
                        rows={3}
                        data-testid="contract-objeto-input"
                    />
                </div>

                {/* Vehicle fields */}
                {(type === 'veiculo_com_motorista' || type === 'veiculo_sem_motorista') && (
                    <>
                        <div className="space-y-2">
                            <Label>Marca do Veículo</Label>
                            <Input
                                value={formData.veiculo_marca}
                                onChange={(e) => handleChange('veiculo_marca', e.target.value)}
                                placeholder="Ex: Toyota"
                                data-testid="contract-veiculo-marca-input"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Modelo</Label>
                            <Input
                                value={formData.veiculo_modelo}
                                onChange={(e) => handleChange('veiculo_modelo', e.target.value)}
                                placeholder="Ex: Corolla"
                                data-testid="contract-veiculo-modelo-input"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Ano</Label>
                            <Input
                                value={formData.veiculo_ano}
                                onChange={(e) => handleChange('veiculo_ano', e.target.value)}
                                placeholder="Ex: 2020"
                                data-testid="contract-veiculo-ano-input"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Placa</Label>
                            <Input
                                value={formData.veiculo_placa}
                                onChange={(e) => handleChange('veiculo_placa', e.target.value)}
                                placeholder="Ex: ABC1234"
                                data-testid="contract-veiculo-placa-input"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>RENAVAM</Label>
                            <Input
                                value={formData.veiculo_renavam}
                                onChange={(e) => handleChange('veiculo_renavam', e.target.value)}
                                data-testid="contract-veiculo-renavam-input"
                            />
                        </div>
                    </>
                )}

                {/* Driver fields for vehicle with driver */}
                {type === 'veiculo_com_motorista' && (
                    <>
                        <div className="space-y-2">
                            <Label>Nome do Motorista</Label>
                            <Input
                                value={formData.motorista_nome}
                                onChange={(e) => handleChange('motorista_nome', e.target.value)}
                                data-testid="contract-motorista-nome-input"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>CNH do Motorista</Label>
                            <Input
                                value={formData.motorista_cnh}
                                onChange={(e) => handleChange('motorista_cnh', e.target.value)}
                                data-testid="contract-motorista-cnh-input"
                            />
                        </div>
                        <div className="space-y-2 md:col-span-2">
                            <Label>Descrição do Reboque/Paredão (se aplicável)</Label>
                            <Input
                                value={formData.reboque_descricao}
                                onChange={(e) => handleChange('reboque_descricao', e.target.value)}
                                data-testid="contract-reboque-descricao-input"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Placa do Reboque</Label>
                            <Input
                                value={formData.reboque_placa}
                                onChange={(e) => handleChange('reboque_placa', e.target.value)}
                                data-testid="contract-reboque-placa-input"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>RENAVAM do Reboque</Label>
                            <Input
                                value={formData.reboque_renavam}
                                onChange={(e) => handleChange('reboque_renavam', e.target.value)}
                                data-testid="contract-reboque-renavam-input"
                            />
                        </div>
                    </>
                )}

                {/* Property fields */}
                {(type === 'imovel_comite' || type === 'imovel') && (
                    <>
                        <div className="space-y-2 md:col-span-2">
                            <Label>Descrição do Imóvel</Label>
                            <Textarea
                                value={formData.imovel_descricao}
                                onChange={(e) => handleChange('imovel_descricao', e.target.value)}
                                placeholder="Ex: 01 terraço, 01 sala, 02 quartos..."
                                rows={2}
                                data-testid="contract-imovel-descricao-input"
                            />
                        </div>
                        <div className="space-y-2 md:col-span-2">
                            <Label>Registro do Imóvel</Label>
                            <Input
                                value={formData.imovel_registro}
                                onChange={(e) => handleChange('imovel_registro', e.target.value)}
                                placeholder="Número do registro no cartório"
                                data-testid="contract-imovel-registro-input"
                            />
                        </div>
                    </>
                )}

                {/* Event space fields */}
                {(type === 'imovel_evento' || type === 'espaco_evento') && (
                    <>
                        <div className="space-y-2">
                            <Label>Horário de Início</Label>
                            <Input
                                type="time"
                                value={formData.evento_horario_inicio}
                                onChange={(e) => handleChange('evento_horario_inicio', e.target.value)}
                                data-testid="contract-evento-inicio-input"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Horário de Término</Label>
                            <Input
                                type="time"
                                value={formData.evento_horario_fim}
                                onChange={(e) => handleChange('evento_horario_fim', e.target.value)}
                                data-testid="contract-evento-fim-input"
                            />
                        </div>
                    </>
                )}
            </>
        );
    };

    return (
        <Layout>
            <div className="space-y-6" data-testid="contratos-page">
                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div>
                        <h1 className="font-heading text-3xl font-bold">Contratos Eleitorais</h1>
                        <p className="text-muted-foreground">Crie contratos com templates prontos e assinatura digital</p>
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
                        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                            <DialogHeader>
                                <DialogTitle className="font-heading">
                                    {editingId ? 'Editar Contrato' : 'Novo Contrato'}
                                </DialogTitle>
                                <DialogDescription>
                                    Preencha os dados do contrato. Os dados do candidato (locatário) serão preenchidos automaticamente.
                                </DialogDescription>
                            </DialogHeader>
                            <form onSubmit={handleSubmit} className="space-y-6 mt-4">
                                <Tabs defaultValue="template" className="w-full">
                                    <TabsList className="grid w-full grid-cols-3">
                                        <TabsTrigger value="template">Template</TabsTrigger>
                                        <TabsTrigger value="locador">Locador (Prestador)</TabsTrigger>
                                        <TabsTrigger value="detalhes">Detalhes</TabsTrigger>
                                    </TabsList>

                                    {/* Template Selection Tab */}
                                    <TabsContent value="template" className="space-y-4 mt-4">
                                        <div className="space-y-2">
                                            <Label>Tipo de Contrato *</Label>
                                            <Select
                                                value={formData.template_type}
                                                onValueChange={handleTemplateChange}
                                            >
                                                <SelectTrigger data-testid="contract-template-select">
                                                    <SelectValue placeholder="Selecione o tipo de contrato" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {contractTemplates.map(template => (
                                                        <SelectItem key={template.value} value={template.value}>
                                                            {template.label}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>

                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            <div className="space-y-2 md:col-span-2">
                                                <Label>Título do Contrato *</Label>
                                                <Input
                                                    value={formData.title}
                                                    onChange={(e) => handleChange('title', e.target.value)}
                                                    required
                                                    data-testid="contract-title-input"
                                                />
                                            </div>

                                            {renderTemplateFields()}
                                        </div>
                                    </TabsContent>

                                    {/* Locador Tab */}
                                    <TabsContent value="locador" className="space-y-4 mt-4">
                                        <div className="bg-muted/50 p-4 rounded-lg mb-4">
                                            <p className="text-sm text-muted-foreground">
                                                <strong>Locador</strong> é o prestador de serviço ou proprietário do bem que será locado.
                                            </p>
                                        </div>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            <div className="space-y-2 md:col-span-2">
                                                <Label>Nome Completo *</Label>
                                                <Input
                                                    value={formData.locador_nome}
                                                    onChange={(e) => handleChange('locador_nome', e.target.value)}
                                                    required
                                                    data-testid="contract-locador-nome-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Nacionalidade</Label>
                                                <Input
                                                    value={formData.locador_nacionalidade}
                                                    onChange={(e) => handleChange('locador_nacionalidade', e.target.value)}
                                                    data-testid="contract-locador-nacionalidade-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Estado Civil</Label>
                                                <Select
                                                    value={formData.locador_estado_civil}
                                                    onValueChange={(v) => handleChange('locador_estado_civil', v)}
                                                >
                                                    <SelectTrigger data-testid="contract-locador-estado-civil-select">
                                                        <SelectValue placeholder="Selecione" />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="Solteiro(a)">Solteiro(a)</SelectItem>
                                                        <SelectItem value="Casado(a)">Casado(a)</SelectItem>
                                                        <SelectItem value="Divorciado(a)">Divorciado(a)</SelectItem>
                                                        <SelectItem value="Viúvo(a)">Viúvo(a)</SelectItem>
                                                        <SelectItem value="União Estável">União Estável</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Profissão</Label>
                                                <Input
                                                    value={formData.locador_profissao}
                                                    onChange={(e) => handleChange('locador_profissao', e.target.value)}
                                                    data-testid="contract-locador-profissao-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>RG</Label>
                                                <Input
                                                    value={formData.locador_rg}
                                                    onChange={(e) => handleChange('locador_rg', e.target.value)}
                                                    data-testid="contract-locador-rg-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>CPF *</Label>
                                                <Input
                                                    value={formData.locador_cpf}
                                                    onChange={(e) => handleChange('locador_cpf', e.target.value)}
                                                    required
                                                    data-testid="contract-locador-cpf-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Email (para assinatura)</Label>
                                                <Input
                                                    type="email"
                                                    value={formData.locador_email}
                                                    onChange={(e) => handleChange('locador_email', e.target.value)}
                                                    data-testid="contract-locador-email-input"
                                                />
                                            </div>
                                            <div className="space-y-2 md:col-span-2">
                                                <Label>Endereço</Label>
                                                <Input
                                                    value={formData.locador_endereco}
                                                    onChange={(e) => handleChange('locador_endereco', e.target.value)}
                                                    placeholder="Rua, Avenida..."
                                                    data-testid="contract-locador-endereco-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Número</Label>
                                                <Input
                                                    value={formData.locador_numero}
                                                    onChange={(e) => handleChange('locador_numero', e.target.value)}
                                                    data-testid="contract-locador-numero-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>CEP</Label>
                                                <Input
                                                    value={formData.locador_cep}
                                                    onChange={(e) => handleChange('locador_cep', e.target.value)}
                                                    data-testid="contract-locador-cep-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Bairro</Label>
                                                <Input
                                                    value={formData.locador_bairro}
                                                    onChange={(e) => handleChange('locador_bairro', e.target.value)}
                                                    data-testid="contract-locador-bairro-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Cidade</Label>
                                                <Input
                                                    value={formData.locador_cidade}
                                                    onChange={(e) => handleChange('locador_cidade', e.target.value)}
                                                    data-testid="contract-locador-cidade-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Estado</Label>
                                                <Input
                                                    value={formData.locador_estado}
                                                    onChange={(e) => handleChange('locador_estado', e.target.value)}
                                                    placeholder="Ex: RN"
                                                    maxLength={2}
                                                    data-testid="contract-locador-estado-input"
                                                />
                                            </div>
                                        </div>
                                    </TabsContent>

                                    {/* Details Tab */}
                                    <TabsContent value="detalhes" className="space-y-4 mt-4">
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                                            
                                            {/* Payment Installments Section */}
                                            <div className="md:col-span-2 p-4 bg-muted/30 rounded-lg space-y-4">
                                                <div className="flex items-center gap-2">
                                                    <DollarSign className="h-5 w-5 text-accent" />
                                                    <h4 className="font-medium">Configuração de Pagamento</h4>
                                                </div>
                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                    <div className="space-y-2">
                                                        <Label>Número de Parcelas</Label>
                                                        <Select
                                                            value={formData.num_parcelas?.toString() || "1"}
                                                            onValueChange={(value) => handleChange('num_parcelas', parseInt(value))}
                                                        >
                                                            <SelectTrigger data-testid="contract-parcelas-select">
                                                                <SelectValue />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                <SelectItem value="1">1 Parcela (À vista)</SelectItem>
                                                                <SelectItem value="2">2 Parcelas (50% + 50%)</SelectItem>
                                                                <SelectItem value="3">3 Parcelas</SelectItem>
                                                                <SelectItem value="4">4 Parcelas</SelectItem>
                                                            </SelectContent>
                                                        </Select>
                                                    </div>
                                                    <div className="flex items-center space-x-2 pt-6">
                                                        <Checkbox
                                                            id="gerar_despesas"
                                                            checked={formData.gerar_despesas}
                                                            onCheckedChange={(checked) => handleChange('gerar_despesas', checked)}
                                                            data-testid="contract-gerar-despesas-checkbox"
                                                        />
                                                        <Label htmlFor="gerar_despesas" className="text-sm">
                                                            Gerar despesas automaticamente (status: pendente)
                                                        </Label>
                                                    </div>
                                                </div>
                                                {formData.num_parcelas > 1 && formData.value && (
                                                    <div className="text-sm text-muted-foreground">
                                                        Valor por parcela: <span className="font-medium text-accent">{formatCurrency(parseFloat(formData.value) / formData.num_parcelas)}</span>
                                                    </div>
                                                )}
                                            </div>
                                            
                                            <div className="space-y-2 md:col-span-2">
                                                <Label>Descrição / Observações</Label>
                                                <Textarea
                                                    value={formData.description}
                                                    onChange={(e) => handleChange('description', e.target.value)}
                                                    rows={3}
                                                    data-testid="contract-description-input"
                                                />
                                            </div>
                                        </div>
                                    </TabsContent>
                                </Tabs>

                                <div className="flex justify-end gap-3 pt-4 border-t">
                                    <Button
                                        type="button"
                                        variant="outline"
                                        onClick={() => setDialogOpen(false)}
                                    >
                                        Cancelar
                                    </Button>
                                    <Button type="submit" disabled={saving} data-testid="contract-submit-btn">
                                        {saving ? 'Salvando...' : editingId ? 'Atualizar' : 'Criar Contrato'}
                                    </Button>
                                </div>
                            </form>
                        </DialogContent>
                    </Dialog>
                </div>

                {/* Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <Card data-testid="contract-total-card">
                        <CardContent className="p-6">
                            <div className="flex items-center gap-4">
                                <div className="w-14 h-14 rounded-xl bg-primary/20 flex items-center justify-center">
                                    <FileText className="h-7 w-7 text-primary" />
                                </div>
                                <div>
                                    <p className="text-sm text-muted-foreground">Valor Total</p>
                                    <p className="font-heading text-2xl font-bold">
                                        {formatCurrency(totalValue)}
                                    </p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    <Card data-testid="contract-active-card">
                        <CardContent className="p-6">
                            <div className="flex items-center gap-4">
                                <div className="w-14 h-14 rounded-xl bg-secondary/20 flex items-center justify-center">
                                    <CheckCircle className="h-7 w-7 text-secondary" />
                                </div>
                                <div>
                                    <p className="text-sm text-muted-foreground">Contratos Ativos</p>
                                    <p className="font-heading text-2xl font-bold text-secondary">
                                        {activeContracts}
                                    </p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                    <Card data-testid="contract-pending-card">
                        <CardContent className="p-6">
                            <div className="flex items-center gap-4">
                                <div className="w-14 h-14 rounded-xl bg-accent/20 flex items-center justify-center">
                                    <Clock className="h-7 w-7 text-accent" />
                                </div>
                                <div>
                                    <p className="text-sm text-muted-foreground">Aguardando Assinatura</p>
                                    <p className="font-heading text-2xl font-bold text-accent">
                                        {pendingSignatures}
                                    </p>
                                </div>
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
                                    placeholder="Buscar por título ou locador..."
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
                                            <TableHead>Locador</TableHead>
                                            <TableHead>Período</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead className="text-right">Valor</TableHead>
                                            <TableHead className="w-40">Ações</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {filteredContracts.map((contract) => (
                                            <TableRow key={contract.id} data-testid={`contract-row-${contract.id}`}>
                                                <TableCell>
                                                    <div>
                                                        <div className="font-medium">{contract.title}</div>
                                                        {contract.template_type && (
                                                            <div className="text-xs text-muted-foreground">
                                                                {contractTemplates.find(t => t.value === contract.template_type)?.label}
                                                            </div>
                                                        )}
                                                    </div>
                                                </TableCell>
                                                <TableCell className="text-muted-foreground">
                                                    {contract.locador_nome || contract.contractor_name}
                                                </TableCell>
                                                <TableCell className="font-mono text-sm">
                                                    {formatDate(contract.start_date)} - {formatDate(contract.end_date)}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge className={statusColorsExtended[contract.status] || statusColors[contract.status]}>
                                                        {contractStatuses.find(s => s.value === contract.status)?.label || contract.status}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-right font-mono font-medium">
                                                    {formatCurrency(contract.value)}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex gap-1">
                                                        {/* View contract expenses */}
                                                        {contract.gerar_despesas !== false && (
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                onClick={() => fetchContractExpenses(contract.id)}
                                                                title="Ver Despesas"
                                                                className="text-accent hover:text-accent"
                                                                data-testid={`expenses-contract-${contract.id}`}
                                                            >
                                                                <DollarSign className="h-4 w-4" />
                                                            </Button>
                                                        )}
                                                        {/* Required attachments button */}
                                                        {contract.template_type && (
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                onClick={() => fetchContractAttachments(contract.id)}
                                                                title="Gerenciar Anexos Obrigatórios"
                                                                className={contract.attachments && Object.keys(contract.attachments || {}).length > 0 ? "text-green-400" : "text-amber-400"}
                                                                data-testid={`attachments-contract-${contract.id}`}
                                                            >
                                                                <FileCheck className="h-4 w-4" />
                                                            </Button>
                                                        )}
                                                        {contract.template_type && (
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                onClick={() => handlePreview(contract)}
                                                                title="Visualizar Contrato"
                                                                data-testid={`preview-contract-${contract.id}`}
                                                            >
                                                                <Eye className="h-4 w-4" />
                                                            </Button>
                                                        )}
                                                        {(contract.status === 'rascunho' || pendingSignatureStatuses.includes(contract.status)) && contract.template_type && (
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                onClick={() => {
                                                                    setSelectedContract(contract);
                                                                    setSignatureEmail(contract.locador_email || '');
                                                                    setSignatureDialogOpen(true);
                                                                }}
                                                                title="Iniciar assinatura externa"
                                                                className="text-accent hover:text-accent"
                                                                data-testid={`request-signature-${contract.id}`}
                                                            >
                                                                <Send className="h-4 w-4" />
                                                            </Button>
                                                        )}
                                                        {pendingSignatureStatuses.includes(contract.status) && (
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                onClick={() => handleUploadSignedContract(contract)}
                                                                title="Anexar contrato assinado"
                                                                className="text-secondary hover:text-secondary"
                                                                data-testid={`sign-contract-${contract.id}`}
                                                            >
                                                                <FileSignature className="h-4 w-4" />
                                                            </Button>
                                                        )}
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

                {/* Preview Dialog */}
                <Dialog open={previewDialogOpen} onOpenChange={setPreviewDialogOpen}>
                    <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                        <DialogHeader>
                            <DialogTitle className="font-heading flex items-center gap-2">
                                <FileText className="h-5 w-5" />
                                Preview do Contrato
                            </DialogTitle>
                        </DialogHeader>
                        <div 
                            className="mt-4 bg-white text-black p-8 rounded-lg"
                            dangerouslySetInnerHTML={{ __html: previewHtml }}
                        />
                        <div className="flex justify-end gap-3 mt-4">
                            <Button variant="outline" onClick={() => setPreviewDialogOpen(false)}>
                                Fechar
                            </Button>
                            <Button 
                                onClick={() => {
                                    const printWindow = window.open('', '_blank');
                                    printWindow.document.write(`
                                        <html>
                                            <head><title>Contrato - ${selectedContract?.title}</title></head>
                                            <body>${previewHtml}</body>
                                        </html>
                                    `);
                                    printWindow.document.close();
                                    printWindow.print();
                                }}
                                className="gap-2"
                            >
                                <Download className="h-4 w-4" />
                                Imprimir/PDF
                            </Button>
                        </div>
                    </DialogContent>
                </Dialog>

                {/* Signature Request Dialog */}
                <Dialog open={signatureDialogOpen} onOpenChange={setSignatureDialogOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle className="font-heading flex items-center gap-2">
                                <Send className="h-5 w-5" />
                                Iniciar Assinatura Externa (Gov.br)
                            </DialogTitle>
                            <DialogDescription>
                                Baixe o contrato, assine no Gov.br e depois anexe o documento final assinado por ambas as partes.
                            </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 mt-4">
                            <div className="space-y-2">
                                <Label>Email do Locador (opcional)</Label>
                                <Input
                                    type="email"
                                    value={signatureEmail}
                                    onChange={(e) => setSignatureEmail(e.target.value)}
                                    placeholder="email@locador.com"
                                    data-testid="signature-email-input"
                                />
                            </div>
                            <p className="text-sm text-muted-foreground">
                                O sistema vai baixar o PDF do contrato e abrir o assinador do Gov.br.
                                Após assinatura do candidato e do prestador, use o botão de anexo na lista para enviar o documento assinado final.
                            </p>
                        </div>
                        <div className="flex justify-end gap-3 mt-4">
                            <Button variant="outline" onClick={() => setSignatureDialogOpen(false)}>
                                Cancelar
                            </Button>
                            <Button onClick={handleRequestSignature} className="gap-2" data-testid="send-signature-request-btn">
                                <Send className="h-4 w-4" />
                                Baixar e Abrir Gov.br
                            </Button>
                        </div>
                    </DialogContent>
                </Dialog>

                {/* Contract Expenses Dialog */}
                <Dialog open={expensesDialogOpen} onOpenChange={setExpensesDialogOpen}>
                    <DialogContent className="max-w-2xl">
                        <DialogHeader>
                            <DialogTitle>
                                Despesas do Contrato
                            </DialogTitle>
                            <DialogDescription>
                                {contractExpenses.contract_title} - {formatCurrency(contractExpenses.total_value || 0)}
                            </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 mt-4">
                            {/* Summary */}
                            <div className="grid grid-cols-2 gap-4">
                                <Card className="bg-green-500/10 border-green-500/30">
                                    <CardContent className="p-4">
                                        <p className="text-sm text-muted-foreground">Total Pago</p>
                                        <p className="text-xl font-bold text-green-400">
                                            {formatCurrency(contractExpenses.total_paid || 0)}
                                        </p>
                                    </CardContent>
                                </Card>
                                <Card className="bg-amber-500/10 border-amber-500/30">
                                    <CardContent className="p-4">
                                        <p className="text-sm text-muted-foreground">Total Pendente</p>
                                        <p className="text-xl font-bold text-amber-400">
                                            {formatCurrency(contractExpenses.total_pending || 0)}
                                        </p>
                                    </CardContent>
                                </Card>
                            </div>
                            
                            {/* Expenses List */}
                            <div className="space-y-2">
                                {contractExpenses.expenses?.map((expense, index) => (
                                    <div 
                                        key={expense.id}
                                        className={`flex items-center justify-between p-3 rounded-lg ${
                                            expense.payment_status === 'pago' 
                                                ? 'bg-green-500/10 border border-green-500/30' 
                                                : 'bg-muted/50 border border-muted'
                                        }`}
                                    >
                                        <div className="flex items-center gap-3">
                                            {expense.payment_status === 'pago' ? (
                                                <CheckCircle className="h-5 w-5 text-green-400" />
                                            ) : (
                                                <Clock className="h-5 w-5 text-amber-400" />
                                            )}
                                            <div>
                                                <p className="font-medium text-sm">{expense.description}</p>
                                                <p className="text-xs text-muted-foreground">
                                                    Vencimento: {formatDate(expense.date)}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <p className={`font-mono font-bold ${expense.payment_status === 'pago' ? 'text-green-400' : 'text-amber-400'}`}>
                                                {formatCurrency(expense.amount)}
                                            </p>
                                            <Badge 
                                                variant="outline" 
                                                className={expense.payment_status === 'pago' ? 'text-green-400 border-green-500/30' : 'text-amber-400 border-amber-500/30'}
                                            >
                                                {expense.payment_status === 'pago' ? 'Pago' : 'Pendente'}
                                            </Badge>
                                        </div>
                                    </div>
                                ))}
                            </div>
                            
                            <p className="text-sm text-muted-foreground">
                                Para marcar uma despesa como paga, anexe o comprovante na página de Despesas.
                            </p>
                        </div>
                        <div className="flex justify-end mt-4">
                            <Button variant="outline" onClick={() => setExpensesDialogOpen(false)}>
                                Fechar
                            </Button>
                        </div>
                    </DialogContent>
                </Dialog>

                {/* Required Attachments Dialog */}
                <Dialog open={attachmentsDialogOpen} onOpenChange={setAttachmentsDialogOpen}>
                    <DialogContent className="max-w-2xl">
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <FileCheck className="h-5 w-5" />
                                Anexos Obrigatórios do Contrato
                            </DialogTitle>
                            <DialogDescription>
                                {selectedContractAttachments?.template_type && (
                                    <span className="capitalize">
                                        Tipo: {contractTemplates.find(t => t.value === selectedContractAttachments.template_type)?.label || selectedContractAttachments.template_type}
                                    </span>
                                )}
                            </DialogDescription>
                        </DialogHeader>
                        
                        {selectedContractAttachments && (
                            <div className="space-y-4 mt-4">
                                {/* Progress */}
                                <div className="space-y-2">
                                    <div className="flex justify-between text-sm">
                                        <span>Progresso dos anexos obrigatórios</span>
                                        <span className={selectedContractAttachments.complete ? "text-green-400" : "text-amber-400"}>
                                            {selectedContractAttachments.total_uploaded}/{selectedContractAttachments.total_required} enviados
                                        </span>
                                    </div>
                                    <Progress 
                                        value={(selectedContractAttachments.total_uploaded / selectedContractAttachments.total_required) * 100} 
                                        className="h-2"
                                    />
                                </div>

                                {/* Warning if incomplete */}
                                {!selectedContractAttachments.complete && (
                                    <div className="flex items-center gap-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                                        <AlertTriangle className="h-5 w-5 text-amber-400" />
                                        <p className="text-sm text-amber-400">
                                            Existem anexos obrigatórios pendentes. Envie todos os documentos necessários.
                                        </p>
                                    </div>
                                )}

                                {/* Attachments List */}
                                <div className="space-y-3">
                                    {selectedContractAttachments.attachments?.map((attachment) => (
                                        <div 
                                            key={attachment.key}
                                            className={`flex items-center justify-between p-3 rounded-lg border ${
                                                attachment.uploaded 
                                                    ? 'bg-green-500/10 border-green-500/30' 
                                                    : attachment.required 
                                                        ? 'bg-amber-500/10 border-amber-500/30'
                                                        : 'bg-muted/50 border-muted'
                                            }`}
                                        >
                                            <div className="flex items-center gap-3">
                                                {attachment.uploaded ? (
                                                    <CheckCircle className="h-5 w-5 text-green-400" />
                                                ) : attachment.required ? (
                                                    <AlertTriangle className="h-5 w-5 text-amber-400" />
                                                ) : (
                                                    <FileText className="h-5 w-5 text-muted-foreground" />
                                                )}
                                                <div>
                                                    <p className="font-medium text-sm">
                                                        {attachment.label}
                                                        {attachment.required && <span className="text-destructive ml-1">*</span>}
                                                    </p>
                                                    {attachment.attachment_info && (
                                                        <p className="text-xs text-muted-foreground">
                                                            {attachment.attachment_info.original_name}
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {attachment.uploaded ? (
                                                    <>
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            className="text-green-400"
                                                            onClick={() => window.open(`${API}/attachments/${attachment.attachment_id}/download`, '_blank')}
                                                        >
                                                            <Download className="h-4 w-4 mr-1" />
                                                            Ver
                                                        </Button>
                                                        <label className="cursor-pointer">
                                                            <input
                                                                type="file"
                                                                accept=".jpg,.jpeg,.png,.pdf"
                                                                className="hidden"
                                                                onChange={(e) => handleUploadSpecificAttachment(
                                                                    selectedContractAttachments.contract_id,
                                                                    attachment.key,
                                                                    e.target.files[0]
                                                                )}
                                                            />
                                                            <Button variant="ghost" size="sm" asChild>
                                                                <span>Substituir</span>
                                                            </Button>
                                                        </label>
                                                    </>
                                                ) : (
                                                    <label className="cursor-pointer">
                                                        <input
                                                            type="file"
                                                            accept=".jpg,.jpeg,.png,.pdf"
                                                            className="hidden"
                                                            onChange={(e) => handleUploadSpecificAttachment(
                                                                selectedContractAttachments.contract_id,
                                                                attachment.key,
                                                                e.target.files[0]
                                                            )}
                                                            disabled={uploadingAttachmentKey === attachment.key}
                                                        />
                                                        <Button 
                                                            variant={attachment.required ? "default" : "outline"} 
                                                            size="sm" 
                                                            asChild
                                                            className={attachment.required ? "bg-accent hover:bg-accent/90" : ""}
                                                        >
                                                            <span>
                                                                {uploadingAttachmentKey === attachment.key ? (
                                                                    <Loader2 className="h-4 w-4 animate-spin mr-1" />
                                                                ) : (
                                                                    <Upload className="h-4 w-4 mr-1" />
                                                                )}
                                                                Enviar
                                                            </span>
                                                        </Button>
                                                    </label>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                <p className="text-xs text-muted-foreground">
                                    * Campos obrigatórios. Formatos aceitos: JPEG, PNG, PDF (máx. 10MB)
                                </p>
                            </div>
                        )}
                        
                        <div className="flex justify-end mt-4">
                            <Button variant="outline" onClick={() => setAttachmentsDialogOpen(false)}>
                                Fechar
                            </Button>
                        </div>
                    </DialogContent>
                </Dialog>
            </div>
        </Layout>
    );
}

