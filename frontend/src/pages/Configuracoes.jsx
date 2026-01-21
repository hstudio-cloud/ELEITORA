import { useState, useEffect } from 'react';
import axios from 'axios';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';
import { User, Vote, Save, Building } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const brazilianStates = [
    'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS',
    'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC',
    'SP', 'SE', 'TO'
];

const positions = [
    'Prefeito', 'Vice-Prefeito', 'Vereador', 'Governador', 'Vice-Governador',
    'Deputado Estadual', 'Deputado Federal', 'Senador', 'Presidente', 'Vice-Presidente'
];

export default function Configuracoes() {
    const { user, fetchUser } = useAuth();
    const [campaign, setCampaign] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    const [campaignForm, setCampaignForm] = useState({
        candidate_name: '',
        party: '',
        position: 'Vereador',
        city: '',
        state: 'SP',
        election_year: new Date().getFullYear()
    });

    useEffect(() => {
        fetchCampaign();
    }, []);

    const fetchCampaign = async () => {
        try {
            const response = await axios.get(`${API}/campaigns/my`);
            if (response.data) {
                setCampaign(response.data);
                setCampaignForm({
                    candidate_name: response.data.candidate_name,
                    party: response.data.party,
                    position: response.data.position,
                    city: response.data.city,
                    state: response.data.state,
                    election_year: response.data.election_year
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

    return (
        <Layout>
            <div className="space-y-6 max-w-4xl" data-testid="configuracoes-page">
                {/* Header */}
                <div>
                    <h1 className="font-heading text-3xl font-bold">Configurações</h1>
                    <p className="text-muted-foreground">Gerencie as configurações do sistema</p>
                </div>

                <Tabs defaultValue="campaign" className="space-y-6">
                    <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="campaign" className="gap-2" data-testid="tab-campaign">
                            <Vote className="h-4 w-4" />
                            Campanha
                        </TabsTrigger>
                        <TabsTrigger value="profile" className="gap-2" data-testid="tab-profile">
                            <User className="h-4 w-4" />
                            Perfil
                        </TabsTrigger>
                    </TabsList>

                    {/* Campaign Tab */}
                    <TabsContent value="campaign">
                        <Card>
                            <CardHeader>
                                <CardTitle className="font-heading flex items-center gap-2">
                                    <Building className="h-5 w-5" />
                                    Dados da Campanha
                                </CardTitle>
                                <CardDescription>
                                    Configure as informações da campanha eleitoral
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                {loading ? (
                                    <div className="text-center py-8 text-muted-foreground">Carregando...</div>
                                ) : (
                                    <form onSubmit={handleSaveCampaign} className="space-y-6">
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
                                                <Label>Partido *</Label>
                                                <Input
                                                    value={campaignForm.party}
                                                    onChange={(e) => handleCampaignChange('party', e.target.value)}
                                                    required
                                                    placeholder="Ex: PARTIDO"
                                                    data-testid="campaign-party-input"
                                                />
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
                                                        {positions.map(pos => (
                                                            <SelectItem key={pos} value={pos}>{pos}</SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
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
                                                        {brazilianStates.map(state => (
                                                            <SelectItem key={state} value={state}>{state}</SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </div>
                                        <div className="flex justify-end">
                                            <Button type="submit" disabled={saving} className="gap-2" data-testid="save-campaign-btn">
                                                <Save className="h-4 w-4" />
                                                {saving ? 'Salvando...' : campaign ? 'Atualizar Campanha' : 'Criar Campanha'}
                                            </Button>
                                        </div>
                                    </form>
                                )}
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
