import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { toast } from 'sonner';
import { formatCurrency } from '../lib/utils';
import { Vote, FileSignature, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AssinarContrato() {
    const { token } = useParams();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(true);
    const [signing, setSigning] = useState(false);
    const [signed, setSigned] = useState(false);
    const [error, setError] = useState(null);
    const [contractData, setContractData] = useState(null);
    const [agreement, setAgreement] = useState(false);
    const [signerName, setSignerName] = useState('');

    useEffect(() => {
        verifyToken();
    }, [token]);

    const verifyToken = async () => {
        try {
            const response = await axios.get(`${API}/contracts/verify/${token}`);
            setContractData(response.data);
            setSignerName(response.data.locador_nome || '');
            
            if (response.data.status === 'ativo' || response.data.status === 'assinado_locador') {
                setSigned(true);
            }
        } catch (err) {
            setError(err.response?.data?.detail || 'Link inválido ou expirado');
        } finally {
            setLoading(false);
        }
    };

    const handleSign = async () => {
        if (!agreement) {
            toast.error('Você precisa concordar com os termos do contrato');
            return;
        }
        if (!signerName.trim()) {
            toast.error('Digite seu nome completo');
            return;
        }

        setSigning(true);

        try {
            // Generate signature hash
            const signatureHash = btoa(`${contractData.contract_id}-locador-${signerName}-${Date.now()}`);
            
            await axios.post(`${API}/contracts/sign-locador/${token}`, {
                signature_hash: signatureHash
            });

            setSigned(true);
            toast.success('Contrato assinado com sucesso!');
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Erro ao assinar contrato');
        } finally {
            setSigning(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="text-center">
                    <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto mb-4" />
                    <p className="text-muted-foreground">Carregando contrato...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center p-4">
                <Card className="max-w-md w-full">
                    <CardContent className="pt-6 text-center">
                        <AlertCircle className="h-16 w-16 text-destructive mx-auto mb-4" />
                        <h2 className="font-heading text-xl font-bold mb-2">Link Inválido</h2>
                        <p className="text-muted-foreground mb-4">{error}</p>
                        <p className="text-sm text-muted-foreground">
                            Se você acredita que isso é um erro, entre em contato com o remetente do contrato.
                        </p>
                    </CardContent>
                </Card>
            </div>
        );
    }

    if (signed) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center p-4">
                <Card className="max-w-md w-full">
                    <CardContent className="pt-6 text-center">
                        <CheckCircle className="h-16 w-16 text-secondary mx-auto mb-4" />
                        <h2 className="font-heading text-xl font-bold mb-2">Contrato Assinado!</h2>
                        <p className="text-muted-foreground mb-4">
                            O contrato foi assinado com sucesso. Uma cópia será enviada para seu email.
                        </p>
                        <div className="bg-muted/50 p-4 rounded-lg text-left text-sm">
                            <p><strong>Locador:</strong> {contractData?.locador_nome}</p>
                            <p><strong>Candidato:</strong> {contractData?.candidate_name}</p>
                            <p><strong>Valor:</strong> {formatCurrency(contractData?.value)}</p>
                        </div>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background" data-testid="assinar-contrato-page">
            {/* Header */}
            <header className="border-b border-border bg-card">
                <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                        <Vote className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                        <h1 className="font-heading font-bold">Eleitora 360</h1>
                        <p className="text-sm text-muted-foreground">Assinatura Digital de Contrato</p>
                    </div>
                </div>
            </header>

            <main className="max-w-4xl mx-auto px-4 py-8">
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Contract Preview */}
                    <div className="lg:col-span-2">
                        <Card>
                            <CardHeader>
                                <CardTitle className="font-heading">Contrato para Assinatura</CardTitle>
                                <CardDescription>
                                    Leia atentamente o contrato antes de assinar
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div 
                                    className="bg-white text-black p-6 rounded-lg max-h-[60vh] overflow-y-auto text-sm"
                                    dangerouslySetInnerHTML={{ __html: contractData?.contract_html }}
                                />
                            </CardContent>
                        </Card>
                    </div>

                    {/* Signature Panel */}
                    <div>
                        <Card className="sticky top-4">
                            <CardHeader>
                                <CardTitle className="font-heading flex items-center gap-2">
                                    <FileSignature className="h-5 w-5" />
                                    Assinar Contrato
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                {/* Contract Summary */}
                                <div className="bg-muted/50 p-4 rounded-lg space-y-2 text-sm">
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Valor:</span>
                                        <span className="font-mono font-bold">{formatCurrency(contractData?.value)}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-muted-foreground">Candidato:</span>
                                        <span className="font-medium">{contractData?.candidate_name}</span>
                                    </div>
                                </div>

                                {/* Signer Name */}
                                <div className="space-y-2">
                                    <Label>Seu Nome Completo *</Label>
                                    <Input
                                        value={signerName}
                                        onChange={(e) => setSignerName(e.target.value)}
                                        placeholder="Digite seu nome completo"
                                        data-testid="signer-name-input"
                                    />
                                </div>

                                {/* Agreement Checkbox */}
                                <div className="flex items-start space-x-3">
                                    <Checkbox
                                        id="agreement"
                                        checked={agreement}
                                        onCheckedChange={setAgreement}
                                        data-testid="agreement-checkbox"
                                    />
                                    <label
                                        htmlFor="agreement"
                                        className="text-sm text-muted-foreground leading-relaxed cursor-pointer"
                                    >
                                        Li e concordo com todos os termos do contrato acima. Estou ciente de que 
                                        esta assinatura digital tem validade jurídica conforme a legislação brasileira.
                                    </label>
                                </div>

                                {/* Sign Button */}
                                <Button
                                    onClick={handleSign}
                                    disabled={signing || !agreement || !signerName.trim()}
                                    className="w-full h-12 gap-2"
                                    data-testid="sign-contract-btn"
                                >
                                    {signing ? (
                                        <>
                                            <Loader2 className="h-5 w-5 animate-spin" />
                                            Assinando...
                                        </>
                                    ) : (
                                        <>
                                            <FileSignature className="h-5 w-5" />
                                            Assinar Contrato
                                        </>
                                    )}
                                </Button>

                                <p className="text-xs text-muted-foreground text-center">
                                    Ao assinar, você concorda com os termos do contrato e confirma 
                                    que todas as informações estão corretas.
                                </p>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </main>
        </div>
    );
}
