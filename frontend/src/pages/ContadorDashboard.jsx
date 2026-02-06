import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { toast } from 'sonner';
import { 
    Building2, Users, FileText, DollarSign, AlertTriangle,
    Plus, Search, LogOut, Eye, UserPlus, Settings, 
    TrendingUp, TrendingDown, Clock, CheckCircle, XCircle,
    Calculator, Download, ChevronRight
} from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function ContadorDashboard() {
    const navigate = useNavigate();
    const [user, setUser] = useState(null);
    const [isAdmin, setIsAdmin] = useState(false);
    const [campaigns, setCampaigns] = useState([]);
    const [professionals, setProfessionals] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedCampaign, setSelectedCampaign] = useState(null);
    const [showInviteModal, setShowInviteModal] = useState(false);
    const [showAssignModal, setShowAssignModal] = useState(false);
    const [inviteData, setInviteData] = useState({
        email: '',
        name: '',
        type: 'contador',
        crc: '',
        crc_state: ''
    });

    useEffect(() => {
        const token = localStorage.getItem('contador_token');
        const userData = localStorage.getItem('contador_user');
        const adminStatus = localStorage.getItem('contador_is_admin');

        if (!token || !userData) {
            navigate('/contador/login');
            return;
        }

        setUser(JSON.parse(userData));
        setIsAdmin(adminStatus === 'true');
        loadData(token, adminStatus === 'true');
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [navigate]);

    const loadData = async (token, admin) => {
        try {
            const config = { headers: { Authorization: `Bearer ${token}` } };

            if (admin) {
                // Admin loads all campaigns and professionals
                const [campaignsRes, professionalsRes] = await Promise.all([
                    axios.get(`${API_URL}/api/admin/contador/all-campaigns`, config),
                    axios.get(`${API_URL}/api/admin/contador/professionals`, config)
                ]);
                setCampaigns(campaignsRes.data.campaigns || []);
                setProfessionals(professionalsRes.data.professionals || []);
            } else {
                // Regular contador loads only their campaigns
                const res = await axios.get(`${API_URL}/api/contador/my-campaigns`, config);
                setCampaigns(res.data.campaigns || []);
            }
        } catch (error) {
            toast.error('Erro ao carregar dados');
            if (error.response?.status === 401) {
                handleLogout();
            }
        } finally {
            setLoading(false);
        }
    };

    const handleLogout = () => {
        localStorage.removeItem('contador_token');
        localStorage.removeItem('contador_user');
        localStorage.removeItem('contador_is_admin');
        navigate('/contador/login');
    };

    const handleInvite = async () => {
        try {
            const token = localStorage.getItem('contador_token');
            const res = await axios.post(
                `${API_URL}/api/admin/contador/invite`,
                inviteData,
                { headers: { Authorization: `Bearer ${token}` } }
            );

            toast.success('Convite enviado com sucesso!');
            if (res.data.temp_password) {
                toast.info(`Senha temporária: ${res.data.temp_password}`, { duration: 10000 });
            }
            setShowInviteModal(false);
            setInviteData({ email: '', name: '', type: 'contador', crc: '', crc_state: '' });
            loadData(token, isAdmin);
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao enviar convite');
        }
    };

    const handleAssignCampaign = async (professionalId, campaignId) => {
        try {
            const token = localStorage.getItem('contador_token');
            await axios.post(
                `${API_URL}/api/admin/contador/assign-campaign?professional_id=${professionalId}&campaign_id=${campaignId}`,
                {},
                { headers: { Authorization: `Bearer ${token}` } }
            );

            toast.success('Campanha atribuída com sucesso!');
            setShowAssignModal(false);
            loadData(token, isAdmin);
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao atribuir campanha');
        }
    };

    const getTotalStats = () => {
        const totalReceitas = campaigns.reduce((acc, c) => acc + (c.financeiro?.total_receitas || c.resumo_financeiro?.total_receitas || 0), 0);
        const totalDespesas = campaigns.reduce((acc, c) => acc + (c.financeiro?.total_despesas || c.resumo_financeiro?.total_despesas || 0), 0);
        return { totalReceitas, totalDespesas, saldo: totalReceitas - totalDespesas };
    };

    const formatCurrency = (value) => {
        return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value || 0);
    };

    const stats = getTotalStats();

    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="animate-pulse text-muted-foreground">Carregando...</div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background" data-testid="contador-dashboard">
            {/* Header */}
            <header className="border-b bg-card/50 backdrop-blur sticky top-0 z-50">
                <div className="container mx-auto px-4 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                            <Building2 className="h-5 w-5 text-emerald-500" />
                        </div>
                        <div>
                            <h1 className="font-heading text-xl font-bold">Portal do Contador</h1>
                            <p className="text-xs text-muted-foreground">Ativa Contabilidade</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-4">
                        <div className="text-right hidden sm:block">
                            <p className="text-sm font-medium">{user?.name}</p>
                            <p className="text-xs text-muted-foreground">
                                {isAdmin ? (
                                    <Badge variant="default" className="bg-emerald-600">Admin</Badge>
                                ) : (
                                    <Badge variant="secondary">Contador</Badge>
                                )}
                            </p>
                        </div>
                        <Button variant="ghost" size="icon" onClick={handleLogout} data-testid="contador-logout">
                            <LogOut className="h-5 w-5" />
                        </Button>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="container mx-auto px-4 py-8">
                {/* Stats Cards */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
                    <Card className="bg-gradient-to-br from-blue-500/10 to-blue-600/5 border-blue-500/20">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-muted-foreground">Campanhas</p>
                                    <p className="text-2xl font-bold">{campaigns.length}</p>
                                </div>
                                <Users className="h-8 w-8 text-blue-500 opacity-50" />
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="bg-gradient-to-br from-emerald-500/10 to-emerald-600/5 border-emerald-500/20">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-muted-foreground">Total Receitas</p>
                                    <p className="text-2xl font-bold text-emerald-600">{formatCurrency(stats.totalReceitas)}</p>
                                </div>
                                <TrendingUp className="h-8 w-8 text-emerald-500 opacity-50" />
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="bg-gradient-to-br from-red-500/10 to-red-600/5 border-red-500/20">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-muted-foreground">Total Despesas</p>
                                    <p className="text-2xl font-bold text-red-600">{formatCurrency(stats.totalDespesas)}</p>
                                </div>
                                <TrendingDown className="h-8 w-8 text-red-500 opacity-50" />
                            </div>
                        </CardContent>
                    </Card>

                    <Card className={`bg-gradient-to-br ${stats.saldo >= 0 ? 'from-emerald-500/10 to-emerald-600/5 border-emerald-500/20' : 'from-red-500/10 to-red-600/5 border-red-500/20'}`}>
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm text-muted-foreground">Saldo Total</p>
                                    <p className={`text-2xl font-bold ${stats.saldo >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                                        {formatCurrency(stats.saldo)}
                                    </p>
                                </div>
                                <DollarSign className="h-8 w-8 text-muted-foreground opacity-50" />
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Admin Actions */}
                {isAdmin && (
                    <div className="flex gap-4 mb-8">
                        <Dialog open={showInviteModal} onOpenChange={setShowInviteModal}>
                            <DialogTrigger asChild>
                                <Button className="gap-2 bg-emerald-600 hover:bg-emerald-700" data-testid="invite-professional-btn">
                                    <UserPlus className="h-4 w-4" />
                                    Convidar Profissional
                                </Button>
                            </DialogTrigger>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>Convidar Profissional</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <Label>Nome</Label>
                                        <Input
                                            value={inviteData.name}
                                            onChange={(e) => setInviteData({ ...inviteData, name: e.target.value })}
                                            placeholder="Nome completo"
                                            data-testid="invite-name-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Email</Label>
                                        <Input
                                            type="email"
                                            value={inviteData.email}
                                            onChange={(e) => setInviteData({ ...inviteData, email: e.target.value })}
                                            placeholder="email@exemplo.com"
                                            data-testid="invite-email-input"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Tipo</Label>
                                        <Select
                                            value={inviteData.type}
                                            onValueChange={(v) => setInviteData({ ...inviteData, type: v })}
                                        >
                                            <SelectTrigger data-testid="invite-type-select">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="contador">Contador</SelectItem>
                                                <SelectItem value="advogado">Advogado</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    {inviteData.type === 'contador' && (
                                        <div className="grid grid-cols-2 gap-4">
                                            <div className="space-y-2">
                                                <Label>CRC</Label>
                                                <Input
                                                    value={inviteData.crc}
                                                    onChange={(e) => setInviteData({ ...inviteData, crc: e.target.value })}
                                                    placeholder="Número CRC"
                                                />
                                            </div>
                                            <div className="space-y-2">
                                                <Label>Estado</Label>
                                                <Input
                                                    value={inviteData.crc_state}
                                                    onChange={(e) => setInviteData({ ...inviteData, crc_state: e.target.value })}
                                                    placeholder="UF"
                                                    maxLength={2}
                                                />
                                            </div>
                                        </div>
                                    )}
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setShowInviteModal(false)}>Cancelar</Button>
                                    <Button onClick={handleInvite} className="bg-emerald-600 hover:bg-emerald-700" data-testid="send-invite-btn">
                                        Enviar Convite
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        <Button variant="outline" className="gap-2" onClick={() => setShowAssignModal(true)} data-testid="assign-campaign-btn">
                            <Settings className="h-4 w-4" />
                            Atribuir Campanhas
                        </Button>
                    </div>
                )}

                {/* Professionals List (Admin Only) */}
                {isAdmin && professionals.length > 0 && (
                    <Card className="mb-8">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Users className="h-5 w-5" />
                                Equipe de Contadores
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {professionals.map((prof) => (
                                    <div 
                                        key={prof.id} 
                                        className="p-4 rounded-lg border bg-card hover:bg-muted/50 transition-colors"
                                    >
                                        <div className="flex items-start justify-between">
                                            <div>
                                                <p className="font-medium">{prof.name}</p>
                                                <p className="text-sm text-muted-foreground">{prof.email}</p>
                                            </div>
                                            <Badge variant={prof.is_admin ? "default" : "secondary"}>
                                                {prof.is_admin ? 'Admin' : prof.type}
                                            </Badge>
                                        </div>
                                        <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                                            <FileText className="h-3 w-3" />
                                            {(prof.campaigns || []).length} campanha(s)
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Campaigns List */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <FileText className="h-5 w-5" />
                            Campanhas {isAdmin ? 'no Sistema' : 'Atribuídas'}
                        </CardTitle>
                        <CardDescription>
                            {campaigns.length === 0 
                                ? 'Nenhuma campanha encontrada' 
                                : `${campaigns.length} campanha(s) encontrada(s)`}
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            {campaigns.map((campaign) => {
                                const financeiro = campaign.financeiro || campaign.resumo_financeiro || {};
                                const saldo = (financeiro.total_receitas || 0) - (financeiro.total_despesas || 0);

                                return (
                                    <div 
                                        key={campaign.id}
                                        className="p-4 rounded-lg border hover:border-primary/50 transition-all cursor-pointer group"
                                        onClick={() => setSelectedCampaign(campaign)}
                                        data-testid={`campaign-card-${campaign.id}`}
                                    >
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <h3 className="font-semibold">{campaign.candidate_name}</h3>
                                                    <Badge variant="outline">{campaign.party}</Badge>
                                                </div>
                                                <p className="text-sm text-muted-foreground">
                                                    {campaign.position} - {campaign.city}/{campaign.state}
                                                </p>
                                            </div>
                                            <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
                                        </div>

                                        <div className="mt-4 grid grid-cols-3 gap-4 text-center">
                                            <div>
                                                <p className="text-xs text-muted-foreground">Receitas</p>
                                                <p className="font-semibold text-emerald-600">
                                                    {formatCurrency(financeiro.total_receitas)}
                                                </p>
                                            </div>
                                            <div>
                                                <p className="text-xs text-muted-foreground">Despesas</p>
                                                <p className="font-semibold text-red-600">
                                                    {formatCurrency(financeiro.total_despesas)}
                                                </p>
                                            </div>
                                            <div>
                                                <p className="text-xs text-muted-foreground">Saldo</p>
                                                <p className={`font-semibold ${saldo >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                                                    {formatCurrency(saldo)}
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>

                {/* Campaign Details Modal */}
                {selectedCampaign && (
                    <Dialog open={!!selectedCampaign} onOpenChange={() => setSelectedCampaign(null)}>
                        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
                            <DialogHeader>
                                <DialogTitle className="flex items-center gap-2">
                                    <FileText className="h-5 w-5" />
                                    {selectedCampaign.candidate_name}
                                </DialogTitle>
                            </DialogHeader>
                            <div className="space-y-6">
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <p className="text-sm text-muted-foreground">Cargo</p>
                                        <p className="font-medium">{selectedCampaign.position}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">Partido</p>
                                        <p className="font-medium">{selectedCampaign.party}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">Cidade</p>
                                        <p className="font-medium">{selectedCampaign.city}/{selectedCampaign.state}</p>
                                    </div>
                                    <div>
                                        <p className="text-sm text-muted-foreground">Ano</p>
                                        <p className="font-medium">{selectedCampaign.election_year}</p>
                                    </div>
                                </div>

                                <Card className="bg-muted/50">
                                    <CardHeader className="pb-2">
                                        <CardTitle className="text-base">Resumo Financeiro</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="grid grid-cols-3 gap-4 text-center">
                                            <div className="p-3 rounded-lg bg-emerald-500/10">
                                                <p className="text-xs text-muted-foreground">Total Receitas</p>
                                                <p className="text-xl font-bold text-emerald-600">
                                                    {formatCurrency((selectedCampaign.financeiro || selectedCampaign.resumo_financeiro)?.total_receitas)}
                                                </p>
                                            </div>
                                            <div className="p-3 rounded-lg bg-red-500/10">
                                                <p className="text-xs text-muted-foreground">Total Despesas</p>
                                                <p className="text-xl font-bold text-red-600">
                                                    {formatCurrency((selectedCampaign.financeiro || selectedCampaign.resumo_financeiro)?.total_despesas)}
                                                </p>
                                            </div>
                                            <div className="p-3 rounded-lg bg-blue-500/10">
                                                <p className="text-xs text-muted-foreground">Saldo</p>
                                                <p className="text-xl font-bold text-blue-600">
                                                    {formatCurrency((selectedCampaign.financeiro || selectedCampaign.resumo_financeiro)?.saldo)}
                                                </p>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>

                                <div className="flex gap-2">
                                    <Button variant="outline" className="flex-1 gap-2">
                                        <Download className="h-4 w-4" />
                                        Exportar SPCE
                                    </Button>
                                    <Button variant="outline" className="flex-1 gap-2">
                                        <FileText className="h-4 w-4" />
                                        Relatório PDF
                                    </Button>
                                </div>
                            </div>
                        </DialogContent>
                    </Dialog>
                )}

                {/* Assign Campaign Modal */}
                {isAdmin && (
                    <Dialog open={showAssignModal} onOpenChange={setShowAssignModal}>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Atribuir Campanha a Profissional</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4 py-4">
                                <p className="text-sm text-muted-foreground">
                                    Selecione uma campanha e um profissional para fazer a atribuição.
                                </p>
                                {professionals.filter(p => !p.is_admin).map((prof) => (
                                    <div key={prof.id} className="p-4 rounded-lg border">
                                        <p className="font-medium">{prof.name}</p>
                                        <p className="text-sm text-muted-foreground mb-2">{prof.email}</p>
                                        <Select onValueChange={(campaignId) => handleAssignCampaign(prof.id, campaignId)}>
                                            <SelectTrigger>
                                                <SelectValue placeholder="Selecionar campanha..." />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {campaigns.filter(c => !(prof.campaigns || []).includes(c.id)).map((c) => (
                                                    <SelectItem key={c.id} value={c.id}>
                                                        {c.candidate_name} - {c.city}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                ))}
                            </div>
                        </DialogContent>
                    </Dialog>
                )}
            </main>
        </div>
    );
}
