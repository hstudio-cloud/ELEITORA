import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ChevronRight, FolderOpen, FileArchive, ArrowLeft, FileText } from 'lucide-react';
import { TaxFileUploadZone } from '../components/TaxFileUploadZone';
import { ImportProgressBar } from '../components/ImportProgressBar';
import { ImportSummary } from '../components/ImportSummary';
import { useAuth } from '../contexts/AuthContext';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function ImportarPrestacaoCont() {
    const navigate = useNavigate();
    const { user, loading } = useAuth();

    const [selectedFile, setSelectedFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isImporting, setIsImporting] = useState(false);
    const [currentStep, setCurrentStep] = useState('');
    const [importSummary, setImportSummary] = useState(null);
    const [validationErrors, setValidationErrors] = useState([]);
    const [scanFile, setScanFile] = useState(null);
    const [scanSummary, setScanSummary] = useState(null);
    const [triageItems, setTriageItems] = useState([]);
    const [isUploadingScan, setIsUploadingScan] = useState(false);
    const [triageFields, setTriageFields] = useState({});

    const handleFileSelected = (file) => {
        // Validate file size (2GB max)
        if (file.size > 2 * 1024 * 1024 * 1024) {
            toast.error('Arquivo muito grande (máx 2GB)');
            return;
        }

        setSelectedFile(file);
        // Automatically load preview when file is selected
        loadPreview(file);
    };

    const loadPreview = async (file) => {
        setIsLoading(true);
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await axios.post(`${API}/import/tse/preview-file`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                timeout: 60000  // 60 seconds timeout
            });

            if (response.data.valid) {
                setPreview(response.data.preview);
                setValidationErrors([]);
                toast.success(`Arquivo validado: ${file.name}`);
            } else {
                setValidationErrors(response.data.errors || []);
                toast.error('Arquivo inválido');
                setPreview(null);
                setSelectedFile(null);
            }
        } catch (error) {
            const message = error.response?.data?.detail || 'Erro ao validar arquivo';
            toast.error(message);
            console.error(error);
            setSelectedFile(null);
            setPreview(null);
        } finally {
            setIsLoading(false);
        }
    };

    const handleExecuteImport = async () => {
        if (!user?.campaign_id) {
            toast.error('Campanha não encontrada. Configure a campanha primeiro.');
            return;
        }

        if (!selectedFile) {
            toast.error('Por favor, selecione um arquivo');
            return;
        }

        setIsImporting(true);
        toast.loading('Importando dados...');

        try {
            setCurrentStep('Descompactando arquivo');
            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('campaign_id', user.campaign_id);

            const response = await axios.post(`${API}/import/tse/execute-file`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                timeout: 120000  // 120 seconds timeout for actual import
            });

            setImportSummary(response.data);
            setCurrentStep('Concluído');
            toast.success('Importação concluída com sucesso!');
        } catch (error) {
            const message = error.response?.data?.detail || 'Erro ao executar importação';
            toast.error(message);
            console.error(error);
        } finally {
            setIsImporting(false);
        }
    };

    const handleViewRecords = () => {
        if (importSummary?.receitas_created > 0) {
            navigate('/receitas');
        } else if (importSummary?.despesas_created > 0) {
            navigate('/despesas');
        } else {
            navigate('/dashboard');
        }
    };

    const handleClose = () => {
        navigate(-1);
    };

    const handleClearFile = () => {
        setSelectedFile(null);
        setPreview(null);
        setValidationErrors([]);
        setImportSummary(null);
    };

    const fetchTriage = async () => {
        try {
            const response = await axios.get(`${API}/import/scan-docs`);
            setTriageItems(response.data.items || []);
        } catch (error) {
            console.error(error);
        }
    };

    useEffect(() => {
        if (user?.campaign_id) {
            fetchTriage();
        }
    }, [user?.campaign_id]);

    const handleScanFileSelected = async (file) => {
        if (file.size > 2 * 1024 * 1024 * 1024) {
            toast.error('Arquivo muito grande (máx 2GB)');
            return;
        }

        if (!user?.campaign_id) {
            toast.error('Campanha não encontrada. Configure a campanha primeiro.');
            return;
        }

        setScanFile(file);
        setIsUploadingScan(true);
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('campaign_id', user.campaign_id);
            const response = await axios.post(`${API}/import/scan-docs/upload`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
                timeout: 120000
            });
            setScanSummary(response.data);
            toast.success('Documentos escaneados enviados para triagem');
            await fetchTriage();
        } catch (error) {
            const message = error.response?.data?.detail || 'Erro ao importar documentos escaneados';
            toast.error(message);
        } finally {
            setIsUploadingScan(false);
        }
    };

    const handleApplyTriage = async (item, kind) => {
        try {
            const fields = triageFields[item.id] || {};
            const payload = {
                triage_id: item.id,
                kind,
                description: fields.description || (item.filename ? `Documento importado - ${item.filename}` : 'Documento importado'),
                amount: fields.amount ? Number(fields.amount) : 0,
                date: fields.date || undefined,
                supplier_name: fields.supplier_name || undefined,
                contractor_name: fields.supplier_name || undefined,
                value: fields.amount ? Number(fields.amount) : 0,
                start_date: fields.date || undefined,
                end_date: fields.date || undefined
            };
            await axios.post(`${API}/import/scan-docs/apply`, payload);
            toast.success('Documento aplicado com sucesso');
            await fetchTriage();
        } catch (error) {
            const message = error.response?.data?.detail || 'Erro ao aplicar documento';
            toast.error(message);
        }
    };

    // Show loading while user is being fetched
    if (loading) {
        return (
            <div className="p-8 text-center">
                <p className="text-muted-foreground">Carregando...</p>
            </div>
        );
    }

    // Show import results
    if (importSummary) {
        return (
            <div className="space-y-8 max-w-4xl mx-auto">
                <div className="space-y-2">
                    <div className="flex items-center gap-3 text-muted-foreground">
                        <Button variant="ghost" size="sm" onClick={() => navigate('/dashboard')}>
                            <ArrowLeft className="h-4 w-4 mr-2" />
                            Voltar ao início
                        </Button>
                        <FolderOpen className="h-5 w-5" />
                        <h1 className="text-3xl font-bold text-foreground">Importação Concluída</h1>
                    </div>
                </div>

                <ImportSummary
                    summary={importSummary}
                    onClose={handleClose}
                    onViewRecords={handleViewRecords}
                />
            </div>
        );
    }

    // Show import progress
    if (isImporting) {
        return (
            <div className="space-y-8 max-w-4xl mx-auto">
                <div className="space-y-2">
                    <div className="flex items-center gap-3 text-muted-foreground">
                        <Button variant="ghost" size="sm" onClick={() => navigate('/dashboard')}>
                            <ArrowLeft className="h-4 w-4 mr-2" />
                            Voltar ao início
                        </Button>
                        <FolderOpen className="h-5 w-5" />
                        <h1 className="text-3xl font-bold text-foreground">Importando Dados...</h1>
                    </div>
                </div>

                <div className="bg-card rounded-lg border border-border p-8">
                    <ImportProgressBar
                        isImporting={isImporting}
                        currentStep={currentStep}
                    />
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-8 max-w-4xl mx-auto">
            {/* Header */}
            <div className="space-y-2">
                <div className="flex items-center gap-3 text-muted-foreground">
                    <Button variant="ghost" size="sm" onClick={() => navigate('/dashboard')}>
                        <ArrowLeft className="h-4 w-4 mr-2" />
                        Voltar ao início
                    </Button>
                    <FolderOpen className="h-5 w-5" />
                    <h1 className="text-3xl font-bold text-foreground">Importar Prestação de Contas</h1>
                </div>
                <p className="text-muted-foreground">
                    Importe dados completos de uma prestação de contas do TSE para o ELEITORA
                </p>
            </div>

            {/* Main Content */}
            <div className="bg-card rounded-lg border border-border p-8">
                {!selectedFile ? (
                    // File not selected - show upload zone
                    <div className="space-y-6">
                        <div>
                            <h2 className="text-xl font-semibold mb-2 text-foreground">
                                O arquivo TSE
                            </h2>
                            <p className="text-muted-foreground mb-4">
                                Arraste ou clique para selecionar o arquivo ZIP com a prestação de contas
                            </p>
                        </div>

                        <TaxFileUploadZone
                            onFileSelected={handleFileSelected}
                            isLoading={isLoading}
                        />

                        {validationErrors.length > 0 && (
                            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                                <p className="text-sm font-medium text-red-900 mb-2">
                                    Erros de Validação:
                                </p>
                                <ul className="space-y-1">
                                    {validationErrors.map((error, idx) => (
                                        <li key={idx} className="text-sm text-red-800">
                                            • {error}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                ) : (
                    // File selected - show preview
                    <div className="space-y-6">
                        <div>
                            <h2 className="text-xl font-semibold mb-2 text-foreground">
                                Revisar Dados
                            </h2>
                            <p className="text-muted-foreground">
                                Verifique os dados que serão importados
                            </p>
                        </div>

                        {/* Selected File Display */}
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <FileArchive className="h-5 w-5 text-blue-600" />
                                    <div>
                                        <p className="text-sm font-medium text-blue-900">{selectedFile.name}</p>
                                        <p className="text-xs text-blue-700">
                                            {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                                        </p>
                                    </div>
                                </div>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleClearFile}
                                    disabled={isLoading}
                                >
                                    Trocar arquivo
                                </Button>
                            </div>
                        </div>

                        {/* Preview Data */}
                        {preview && (
                            <div>
                                <p className="text-sm font-medium text-foreground mb-3">
                                    Resumo dos dados:
                                </p>
                                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                                    <div className="bg-muted/50 rounded-lg p-3 border border-border">
                                        <p className="text-2xl font-bold text-primary">
                                            {preview.receitas_count || 0}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1">Receitas</p>
                                    </div>
                                    <div className="bg-muted/50 rounded-lg p-3 border border-border">
                                        <p className="text-2xl font-bold text-primary">
                                            {preview.despesas_count || 0}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1">Despesas</p>
                                    </div>
                                    <div className="bg-muted/50 rounded-lg p-3 border border-border">
                                        <p className="text-2xl font-bold text-primary">
                                            {preview.banco_count || 0}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1">Extratos</p>
                                    </div>
                                    <div className="bg-muted/50 rounded-lg p-3 border border-border">
                                        <p className="text-2xl font-bold text-primary">
                                            {preview.representantes ? Object.keys(preview.representantes).length : 0}
                                        </p>
                                        <p className="text-xs text-muted-foreground mt-1">Representantes</p>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Samples */}
                        {preview?.receitas_sample && preview.receitas_sample.length > 0 && (
                            <div>
                                <p className="text-sm font-medium text-foreground mb-2">Amostra de Receitas:</p>
                                <div className="bg-muted/30 rounded-md p-3 space-y-1">
                                    {preview.receitas_sample.slice(0, 3).map((file, idx) => (
                                        <p key={idx} className="text-xs text-muted-foreground font-mono">
                                            {file}
                                        </p>
                                    ))}
                                </div>
                            </div>
                        )}

                        {preview?.despesas_sample && preview.despesas_sample.length > 0 && (
                            <div>
                                <p className="text-sm font-medium text-foreground mb-2">Amostra de Despesas:</p>
                                <div className="bg-muted/30 rounded-md p-3 space-y-1">
                                    {preview.despesas_sample.slice(0, 3).map((file, idx) => (
                                        <p key={idx} className="text-xs text-muted-foreground font-mono">
                                            {file}
                                        </p>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Scanned Docs Triage */}
            <div className="bg-card rounded-lg border border-border p-8">
                <div className="flex items-center gap-2 text-muted-foreground mb-4">
                    <FileText className="h-5 w-5" />
                    <h2 className="text-xl font-semibold text-foreground">Documentos escaneados (triagem)</h2>
                </div>
                <p className="text-muted-foreground mb-4">
                    Envie o ZIP da campanha 2024 com documentos escaneados para triagem manual.
                </p>

                <TaxFileUploadZone
                    onFileSelected={handleScanFileSelected}
                    isLoading={isUploadingScan}
                />

                {scanSummary && (
                    <div className="mt-4 text-sm text-muted-foreground">
                        Importados: {scanSummary.created || 0} | Ignorados: {scanSummary.skipped || 0}
                    </div>
                )}

                {triageItems.length > 0 && (
                    <div className="mt-6 space-y-3">
                        {triageItems.map((item) => (
                            <div key={item.id} className="border border-border rounded-lg p-4 flex flex-col gap-3">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-sm font-medium text-foreground">{item.filename}</p>
                                        <p className="text-xs text-muted-foreground">
                                            Sugestão: {item.suggested_kind || 'desconhecido'}
                                        </p>
                                    </div>
                                    <div className="flex gap-2 flex-wrap">
                                        <Button size="sm" variant="outline" onClick={() => handleApplyTriage(item, 'expense')}>
                                            Criar despesa
                                        </Button>
                                        <Button size="sm" variant="outline" onClick={() => handleApplyTriage(item, 'contract')}>
                                            Criar contrato
                                        </Button>
                                        <Button size="sm" variant="outline" onClick={() => handleApplyTriage(item, 'revenue')}>
                                            Criar receita
                                        </Button>
                                    </div>
                                </div>
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                    <div className="space-y-1">
                                        <Label className="text-xs">Valor</Label>
                                        <Input
                                            type="number"
                                            step="0.01"
                                            value={triageFields[item.id]?.amount || ''}
                                            onChange={(e) => setTriageFields(prev => ({
                                                ...prev,
                                                [item.id]: { ...prev[item.id], amount: e.target.value }
                                            }))}
                                            placeholder="0,00"
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <Label className="text-xs">Data</Label>
                                        <Input
                                            type="date"
                                            value={triageFields[item.id]?.date || ''}
                                            onChange={(e) => setTriageFields(prev => ({
                                                ...prev,
                                                [item.id]: { ...prev[item.id], date: e.target.value }
                                            }))}
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <Label className="text-xs">Fornecedor</Label>
                                        <Input
                                            value={triageFields[item.id]?.supplier_name || ''}
                                            onChange={(e) => setTriageFields(prev => ({
                                                ...prev,
                                                [item.id]: { ...prev[item.id], supplier_name: e.target.value }
                                            }))}
                                            placeholder="Nome do fornecedor"
                                        />
                                    </div>
                                </div>
                                {item.extracted_text && (
                                    <div className="text-xs text-muted-foreground line-clamp-3">
                                        {item.extracted_text}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Action Buttons */}
            {selectedFile && !isImporting && !importSummary && (
                <div className="flex gap-3 flex-wrap justify-end">
                    <Button
                        variant="outline"
                        onClick={handleClearFile}
                        disabled={isLoading}
                    >
                        Cancelar
                    </Button>
                    <Button
                        onClick={handleExecuteImport}
                        disabled={isLoading || !preview}
                        className="bg-green-600 hover:bg-green-700"
                    >
                        Importar Agora
                        <ChevronRight className="h-4 w-4 ml-2" />
                    </Button>
                </div>
            )}
        </div>
    );
}
