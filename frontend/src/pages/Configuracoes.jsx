import { useState, useEffect } from 'react';
import axios from 'axios';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Separator } from '../components/ui/separator';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { User, Vote, Save, Building, CreditCard, MapPin, AlertCircle } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Configuracoes() {
    const { user, fetchUser } = useAuth();
    const [campaign, setCampaign] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    
    // Reference data
    const [partidos, setPartidos] = useState([]);
    const [estados, setEstados] = useState([]);
    const [bancos, setBancos] = useState([]);
    const [cargos, setCargos] = useState([]);

    const [campaignForm, setCampaignForm] = useState({
        candidate_name: '',
        party: '',
        position: 'Vereador',
        city: '',
        state: 'SP',
        election_year: new Date().getFullYear(),
        // SPCE Required Fields
        cnpj: '',
        numero_candidato: '',
        cpf_candidato: '',
        titulo_eleitor: '',
        // Bank accounts
        conta_doacao_banco: '',
        conta_doacao_agencia: '',
        conta_doacao_numero: '',
        conta_doacao_digito: '',
        conta_fundo_partidario_banco: '',
        conta_fundo_partidario_agencia: '',
        conta_fundo_partidario_numero: '',
        conta_fundo_partidario_digito: '',
        conta_fefec_banco: '',
        conta_fefec_agencia: '',
        conta_fefec_numero: '',
        conta_fefec_digito: '',
        // Address
        endereco: '',
        numero: '',
        complemento: '',
        bairro: '',
        cep: '',
        telefone: '',
        email: ''
    });

    useEffect(() => {
        fetchReferenceData();
        fetchCampaign();
    }, []);

    const fetchReferenceData = async () => {
        try {
            const [partidosRes, estadosRes, bancosRes, cargosRes] = await Promise.all([
                axios.get(`${API}/reference/partidos`),
                axios.get(`${API}/reference/estados`),
                axios.get(`${API}/reference/bancos`),
                axios.get(`${API}/reference/cargos`)
            ]);
            setPartidos(partidosRes.data.partidos);
            setEstados(estadosRes.data.estados);
            setBancos(bancosRes.data.bancos);
            setCargos(cargosRes.data.cargos);
        } catch (error) {
            console.error('Error fetching reference data:', error);
        }
    };

    const fetchCampaign = async () => {
        try {
            const response = await axios.get(`${API}/campaigns/my`);
            if (response.data) {
                setCampaign(response.data);
                setCampaignForm({
                    candidate_name: response.data.candidate_name || '',
                    party: response.data.party || '',
                    position: response.data.position || 'Vereador',
                    city: response.data.city || '',
                    state: response.data.state || 'SP',
                    election_year: response.data.election_year || new Date().getFullYear(),
                    cnpj: response.data.cnpj || '',
                    numero_candidato: response.data.numero_candidato || '',
                    cpf_candidato: response.data.cpf_candidato || '',
                    titulo_eleitor: response.data.titulo_eleitor || '',
                    conta_doacao_banco: response.data.conta_doacao_banco || '',
                    conta_doacao_agencia: response.data.conta_doacao_agencia || '',
                    conta_doacao_numero: response.data.conta_doacao_numero || '',
                    conta_doacao_digito: response.data.conta_doacao_digito || '',
                    conta_fundo_partidario_banco: response.data.conta_fundo_partidario_banco || '',
                    conta_fundo_partidario_agencia: response.data.conta_fundo_partidario_agencia || '',
                    conta_fundo_partidario_numero: response.data.conta_fundo_partidario_numero || '',
                    conta_fundo_partidario_digito: response.data.conta_fundo_partidario_digito || '',
                    conta_fefec_banco: response.data.conta_fefec_banco || '',
                    conta_fefec_agencia: response.data.conta_fefec_agencia || '',
                    conta_fefec_numero: response.data.conta_fefec_numero || '',
                    conta_fefec_digito: response.data.conta_fefec_digito || '',
                    endereco: response.data.endereco || '',
                    numero: response.data.numero || '',
                    complemento: response.data.complemento || '',
                    bairro: response.data.bairro || '',
                    cep: response.data.cep || '',
                    telefone: response.data.telefone || '',
                    email: response.data.email || ''
                });
            }
        } catch (error) {
            console.error('Error fetching campaign:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleCampaignChange = (field, value) => {
        setCampaignForm(prev => ({ ...prev, [field]: value }));
    };

    const handleSaveCampaign = async (e) => {
        e.preventDefault();
        setSaving(true);

        try {
            if (campaign) {
                await axios.put(`${API}/campaigns/${campaign.id}`, campaignForm);
                toast.success('Campanha atualizada!');
            } else {
                await axios.post(`${API}/campaigns`, campaignForm);
                toast.success('Campanha criada!');
                await fetchUser();
            }
            await fetchCampaign();
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao salvar campanha');
        } finally {
            setSaving(false);
        }
    };

    const checkMissingFields = () => {
        const required = ['cnpj', 'cpf_candidato', 'conta_doacao_banco', 'conta_doacao_agencia', 'conta_doacao_numero'];
        const missing = required.filter(field => !campaignForm[field]);
        return missing;
    };

    const missingFields = checkMissingFields();

    return (
        <Layout>
            <div className="space-y-6" data-testid="configuracoes-page">
                {/* Header */}
                <div>
                    <h1 className="font-heading text-3xl font-bold">Configurações</h1>
                    <p className="text-muted-foreground">Configure os dados da campanha para exportação SPCE</p>
                </div>

                {/* Warning for missing fields */}
                {campaign && missingFields.length > 0 && (
                    <Card className="border-accent">
                        <CardContent className="p-4">
                            <div className="flex items-start gap-3">
                                <AlertCircle className="h-5 w-5 text-accent mt-0.5" />
                                <div>
                                    <p className="font-medium text-accent">Dados obrigatórios pendentes</p>
                                    <p className="text-sm text-muted-foreground">
                                        Para exportar a prestação de contas para o SPCE, preencha: CNPJ, CPF do candidato e dados bancários.
                                    </p>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                )}

                <Tabs defaultValue="campaign" className="space-y-6">
                    <TabsList className="grid w-full grid-cols-4">
                        <TabsTrigger value="campaign" className="gap-2" data-testid="tab-campaign">
                            <Vote className="h-4 w-4" />
                            Candidato
                        </TabsTrigger>
                        <TabsTrigger value="banks" className="gap-2" data-testid="tab-banks">
                            <CreditCard className="h-4 w-4" />
                            Contas Bancárias
                        </TabsTrigger>
                        <TabsTrigger value="address" className="gap-2" data-testid="tab-address">
                            <MapPin className="h-4 w-4" />
                            Endereço
                        </TabsTrigger>
                        <TabsTrigger value="profile" className="gap-2" data-testid="tab-profile">
                            <User className="h-4 w-4" />
                            Perfil
                        </TabsTrigger>
                    </TabsList>

                    {/* Campaign/Candidate Tab */}
                    <TabsContent value="campaign">
                        <Card>
                            <CardHeader>
                                <CardTitle className="font-heading flex items-center gap-2">
                                    <Building className="h-5 w-5" />
                                    Dados do Candidato e Campanha
                                </CardTitle>
                                <CardDescription>
                                    Informações obrigatórias para o SPCE da Justiça Eleitoral
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                {loading ? (
                                    <div className="text-center py-8 text-muted-foreground">Carregando...</div>
                                ) : (
                                    <form onSubmit={handleSaveCampaign} className="space-y-6">
                                        {/* Basic Info */}
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                            <div className="space-y-2">
                                                <Label>Nome do Candidato *</Label>
                                                <Input
                                                    value={campaignForm.candidate_name}
                                                    onChange={(e) => handleCampaignChange('candidate_name', e.target.value)}
                                                    required
                                                    placeholder="Nome completo"
                                                    data-testid="campaign-candidate-name-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Número do Candidato</Label>
                                                <Input
                                                    value={campaignForm.numero_candidato}
                                                    onChange={(e) => handleCampaignChange('numero_candidato', e.target.value)}
                                                    placeholder="Ex: 12345"
                                                    data-testid="campaign-numero-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>CPF do Candidato *</Label>
                                                <Input
                                                    value={campaignForm.cpf_candidato}
                                                    onChange={(e) => handleCampaignChange('cpf_candidato', e.target.value)}
                                                    placeholder="000.000.000-00"
                                                    data-testid="campaign-cpf-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Título de Eleitor</Label>
                                                <Input
                                                    value={campaignForm.titulo_eleitor}
                                                    onChange={(e) => handleCampaignChange('titulo_eleitor', e.target.value)}
                                                    placeholder="Número do título"
                                                    data-testid="campaign-titulo-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>CNPJ da Campanha *</Label>
                                                <Input
                                                    value={campaignForm.cnpj}
                                                    onChange={(e) => handleCampaignChange('cnpj', e.target.value)}
                                                    placeholder="00.000.000/0000-00"
                                                    data-testid="campaign-cnpj-input"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Ano da Eleição *</Label>
                                                <Input
                                                    type="number"
                                                    value={campaignForm.election_year}
                                                    onChange={(e) => handleCampaignChange('election_year', parseInt(e.target.value))}
                                                    required
                                                    min="2024"
                                                    max="2100"
                                                    data-testid="campaign-year-input"
                                                />
                                            </div>
                                        </div>

                                        <Separator />

                                        {/* Party and Position */}
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                            <div className="space-y-2">
                                                <Label>Partido *</Label>
                                                <Select
                                                    value={campaignForm.party}
                                                    onValueChange={(value) => handleCampaignChange('party', value)}
                                                >
                                                    <SelectTrigger data-testid="campaign-party-select">
                                                        <SelectValue placeholder="Selecione o partido" />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {partidos.map(p => (
                                                            <SelectItem key={p.sigla} value={p.sigla}>
                                                                {p.sigla} - {p.nome} ({p.numero})
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Cargo *</Label>
                                                <Select
                                                    value={campaignForm.position}
                                                    onValueChange={(value) => handleCampaignChange('position', value)}
                                                >
                                                    <SelectTrigger data-testid="campaign-position-select">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {cargos.map(c => (
                                                            <SelectItem key={c.codigo} value={c.nome}>{c.nome}</SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Estado *</Label>
                                                <Select
                                                    value={campaignForm.state}
                                                    onValueChange={(value) => handleCampaignChange('state', value)}
                                                >
                                                    <SelectTrigger data-testid="campaign-state-select">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {estados.map(e => (
                                                            <SelectItem key={e.uf} value={e.uf}>
                                                                {e.uf} - {e.nome} ({e.regiao})
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Cidade *</Label>
                                                <Input
                                                    value={campaignForm.city}
                                                    onChange={(e) => handleCampaignChange('city', e.target.value)}
                                                    required
                                                    placeholder="Nome da cidade"
                                                    data-testid="campaign-city-input"
                                                />
                                            </div>
                                        </div>

                                        <div className="flex justify-end">
                                            <Button type="submit" disabled={saving} className="gap-2" data-testid="save-campaign-btn">
                                                <Save className="h-4 w-4" />
                                                {saving ? 'Salvando...' : campaign ? 'Atualizar' : 'Criar Campanha'}
                                            </Button>
                                        </div>
                                    </form>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Bank Accounts Tab */}
                    <TabsContent value="banks">
                        <div className="space-y-6">
                            {/* Conta de Doação */}
                            <Card>
                                <CardHeader>
                                    <CardTitle className="font-heading text-lg flex items-center gap-2">
                                        <CreditCard className="h-5 w-5 text-secondary" />
                                        Conta de Doação (Outros Recursos)
                                    </CardTitle>
                                    <CardDescription>
                                        Conta para recebimento de doações de pessoas físicas e recursos próprios
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                                        <div className="space-y-2">
                                            <Label>Banco *</Label>
                                            <Select
                                                value={campaignForm.conta_doacao_banco}
                                                onValueChange={(value) => handleCampaignChange('conta_doacao_banco', value)}
                                            >
                                                <SelectTrigger data-testid="conta-doacao-banco-select">
                                                    <SelectValue placeholder="Selecione" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {bancos.map(b => (
                                                        <SelectItem key={b.codigo} value={b.codigo}>
                                                            {b.codigo} - {b.nome}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Agência *</Label>
                                            <Input
                                                value={campaignForm.conta_doacao_agencia}
                                                onChange={(e) => handleCampaignChange('conta_doacao_agencia', e.target.value)}
                                                placeholder="0000"
                                                data-testid="conta-doacao-agencia-input"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Conta *</Label>
                                            <Input
                                                value={campaignForm.conta_doacao_numero}
                                                onChange={(e) => handleCampaignChange('conta_doacao_numero', e.target.value)}
                                                placeholder="00000000"
                                                data-testid="conta-doacao-numero-input"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Dígito</Label>
                                            <Input
                                                value={campaignForm.conta_doacao_digito}
                                                onChange={(e) => handleCampaignChange('conta_doacao_digito', e.target.value)}
                                                placeholder="0"
                                                maxLength={2}
                                                data-testid="conta-doacao-digito-input"
                                            />
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Conta do Fundo Partidário */}
                            <Card>
                                <CardHeader>
                                    <CardTitle className="font-heading text-lg flex items-center gap-2">
                                        <CreditCard className="h-5 w-5 text-primary" />
                                        Conta do Fundo Partidário
                                    </CardTitle>
                                    <CardDescription>
                                        Conta para recebimento de recursos do fundo partidário
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                                        <div className="space-y-2">
                                            <Label>Banco</Label>
                                            <Select
                                                value={campaignForm.conta_fundo_partidario_banco}
                                                onValueChange={(value) => handleCampaignChange('conta_fundo_partidario_banco', value)}
                                            >
                                                <SelectTrigger data-testid="conta-fundo-banco-select">
                                                    <SelectValue placeholder="Selecione" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {bancos.map(b => (
                                                        <SelectItem key={b.codigo} value={b.codigo}>
                                                            {b.codigo} - {b.nome}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Agência</Label>
                                            <Input
                                                value={campaignForm.conta_fundo_partidario_agencia}
                                                onChange={(e) => handleCampaignChange('conta_fundo_partidario_agencia', e.target.value)}
                                                placeholder="0000"
                                                data-testid="conta-fundo-agencia-input"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Conta</Label>
                                            <Input
                                                value={campaignForm.conta_fundo_partidario_numero}
                                                onChange={(e) => handleCampaignChange('conta_fundo_partidario_numero', e.target.value)}
                                                placeholder="00000000"
                                                data-testid="conta-fundo-numero-input"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Dígito</Label>
                                            <Input
                                                value={campaignForm.conta_fundo_partidario_digito}
                                                onChange={(e) => handleCampaignChange('conta_fundo_partidario_digito', e.target.value)}
                                                placeholder="0"
                                                maxLength={2}
                                                data-testid="conta-fundo-digito-input"
                                            />
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* Conta FEFEC */}
                            <Card>
                                <CardHeader>
                                    <CardTitle className="font-heading text-lg flex items-center gap-2">
                                        <CreditCard className="h-5 w-5 text-accent" />
                                        Conta FEFEC (Fundo Especial de Financiamento de Campanha)
                                    </CardTitle>
                                    <CardDescription>
                                        Conta para recebimento de recursos do fundo eleitoral
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                                        <div className="space-y-2">
                                            <Label>Banco</Label>
                                            <Select
                                                value={campaignForm.conta_fefec_banco}
                                                onValueChange={(value) => handleCampaignChange('conta_fefec_banco', value)}
                                            >
                                                <SelectTrigger data-testid="conta-fefec-banco-select">
                                                    <SelectValue placeholder="Selecione" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {bancos.map(b => (
                                                        <SelectItem key={b.codigo} value={b.codigo}>
                                                            {b.codigo} - {b.nome}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Agência</Label>
                                            <Input
                                                value={campaignForm.conta_fefec_agencia}
                                                onChange={(e) => handleCampaignChange('conta_fefec_agencia', e.target.value)}
                                                placeholder="0000"
                                                data-testid="conta-fefec-agencia-input"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Conta</Label>
                                            <Input
                                                value={campaignForm.conta_fefec_numero}
                                                onChange={(e) => handleCampaignChange('conta_fefec_numero', e.target.value)}
                                                placeholder="00000000"
                                                data-testid="conta-fefec-numero-input"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Dígito</Label>
                                            <Input
                                                value={campaignForm.conta_fefec_digito}
                                                onChange={(e) => handleCampaignChange('conta_fefec_digito', e.target.value)}
                                                placeholder="0"
                                                maxLength={2}
                                                data-testid="conta-fefec-digito-input"
                                            />
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            <div className="flex justify-end">
                                <Button onClick={handleSaveCampaign} disabled={saving} className="gap-2">
                                    <Save className="h-4 w-4" />
                                    {saving ? 'Salvando...' : 'Salvar Contas Bancárias'}
                                </Button>
                            </div>
                        </div>
                    </TabsContent>

                    {/* Address Tab */}
                    <TabsContent value="address">
                        <Card>
                            <CardHeader>
                                <CardTitle className="font-heading flex items-center gap-2">
                                    <MapPin className="h-5 w-5" />
                                    Endereço da Campanha
                                </CardTitle>
                                <CardDescription>
                                    Endereço do comitê ou sede de campanha
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <form onSubmit={handleSaveCampaign} className="space-y-6">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="space-y-2 md:col-span-2">
                                            <Label>Endereço</Label>
                                            <Input
                                                value={campaignForm.endereco}
                                                onChange={(e) => handleCampaignChange('endereco', e.target.value)}
                                                placeholder="Rua, Avenida..."
                                                data-testid="campaign-endereco-input"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Número</Label>
                                            <Input
                                                value={campaignForm.numero}
                                                onChange={(e) => handleCampaignChange('numero', e.target.value)}
                                                placeholder="123"
                                                data-testid="campaign-numero-end-input"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Complemento</Label>
                                            <Input
                                                value={campaignForm.complemento}
                                                onChange={(e) => handleCampaignChange('complemento', e.target.value)}
                                                placeholder="Sala, Andar..."
                                                data-testid="campaign-complemento-input"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Bairro</Label>
                                            <Input
                                                value={campaignForm.bairro}
                                                onChange={(e) => handleCampaignChange('bairro', e.target.value)}
                                                placeholder="Nome do bairro"
                                                data-testid="campaign-bairro-input"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>CEP</Label>
                                            <Input
                                                value={campaignForm.cep}
                                                onChange={(e) => handleCampaignChange('cep', e.target.value)}
                                                placeholder="00000-000"
                                                data-testid="campaign-cep-input"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Telefone</Label>
                                            <Input
                                                value={campaignForm.telefone}
                                                onChange={(e) => handleCampaignChange('telefone', e.target.value)}
                                                placeholder="(00) 00000-0000"
                                                data-testid="campaign-telefone-input"
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Email</Label>
                                            <Input
                                                type="email"
                                                value={campaignForm.email}
                                                onChange={(e) => handleCampaignChange('email', e.target.value)}
                                                placeholder="campanha@email.com"
                                                data-testid="campaign-email-input"
                                            />
                                        </div>
                                    </div>
                                    <div className="flex justify-end">
                                        <Button type="submit" disabled={saving} className="gap-2">
                                            <Save className="h-4 w-4" />
                                            {saving ? 'Salvando...' : 'Salvar Endereço'}
                                        </Button>
                                    </div>
                                </form>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Profile Tab */}
                    <TabsContent value="profile">
                        <Card>
                            <CardHeader>
                                <CardTitle className="font-heading flex items-center gap-2">
                                    <User className="h-5 w-5" />
                                    Informações do Perfil
                                </CardTitle>
                                <CardDescription>
                                    Visualize suas informações de conta
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-6">
                                    <div className="flex items-center gap-4">
                                        <div className="w-20 h-20 rounded-full bg-primary/20 flex items-center justify-center">
                                            <span className="text-2xl font-bold text-primary">
                                                {user?.name?.charAt(0)?.toUpperCase() || 'U'}
                                            </span>
                                        </div>
                                        <div>
                                            <h3 className="text-xl font-semibold">{user?.name}</h3>
                                            <p className="text-muted-foreground capitalize">{user?.role}</p>
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="space-y-2">
                                            <Label>Email</Label>
                                            <Input value={user?.email || ''} disabled data-testid="profile-email-input" />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>CPF</Label>
                                            <Input value={user?.cpf || 'Não informado'} disabled data-testid="profile-cpf-input" />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Telefone</Label>
                                            <Input value={user?.phone || 'Não informado'} disabled data-testid="profile-phone-input" />
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Tipo de Usuário</Label>
                                            <Input value={user?.role === 'candidato' ? 'Candidato' : 'Contador'} disabled data-testid="profile-role-input" />
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>
            </div>
        </Layout>
    );
}
