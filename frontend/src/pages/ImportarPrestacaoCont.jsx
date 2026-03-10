import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { ChevronRight, ChevronLeft, FolderOpen } from 'lucide-react';
import { TaxFileUploadZone } from '../components/TaxFileUploadZone';
import { ImportProgressBar } from '../components/ImportProgressBar';
import { ImportSummary } from '../components/ImportSummary';
import { useAuth } from '../contexts/AuthContext';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function ImportarPrestacaoCont() {
    const navigate = useNavigate();
    const { campaign } = useAuth();

    const [step, setStep] = useState(1); // 1: Folder selection, 2: Validation, 3: Preview, 4: Confirmation
    const [folderPath, setFolderPath] = useState('');
    const [validation, setValidation] = useState(null);
    const [preview, setPreview] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isImporting, setIsImporting] = useState(false);
    const [currentStep, setCurrentStep] = useState('');
    const [importSummary, setImportSummary] = useState(null);
    const [validationErrors, setValidationErrors] = useState([]);

    const handleFolderSelected = (path) => {
        setFolderPath(path);
    };

    const handleValidate = async () => {
        if (!folderPath.trim()) {
            toast.error('Por favor, selecione uma pasta');
            return;
        }

        setIsLoading(true);
        try {
            const response = await axios.post(`${API}/import/tse/validate`, null, {
                params: { folder_path: folderPath }
            });

            if (response.data.valid) {
                setValidation(response.data);
                setValidationErrors([]);
                toast.success('Estrutura TSE validada com sucesso!');
                setStep(2);
            } else {
                setValidationErrors(response.data.errors || []);
                toast.error('Pasta inválida');
                setValidation(response.data);
            }
        } catch (error) {
            const message = error.response?.data?.detail || 'Erro ao validar pasta';
            toast.error(message);
            console.error(error);
        } finally {
            setIsLoading(false);
        }
    };

    const handlePreview = async () => {
        setIsLoading(true);
        try {
            const response = await axios.post(`${API}/import/tse/preview`, null, {
                params: { folder_path: folderPath }
            });

            if (response.data.valid) {
                setPreview(response.data.preview);
                toast.success('Preview carregado com sucesso!');
                setStep(3);
            } else {
                toast.error('Erro ao carregar preview');
            }
        } catch (error) {
            const message = error.response?.data?.detail || 'Erro ao carregar preview';
            toast.error(message);
            console.error(error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleExecuteImport = async () => {
        if (!campaign?._id) {
            toast.error('Campanha não encontrada');
            return;
        }

        setIsImporting(true);
        setStep(4);

        try {
            setCurrentStep('Validando estrutura');
            const response = await axios.post(`${API}/import/tse/execute`, null, {
                params: {
                    folder_path: folderPath,
                    campaign_id: campaign._id
                }
            });

            setImportSummary(response.data);
            setCurrentStep('Concluído');
        } catch (error) {
            const message = error.response?.data?.detail || 'Erro ao executar importação';
            toast.error(message);
            console.error(error);
            setStep(3); // Back to preview
        } finally {
            setIsImporting(false);
        }
    };

    const handleViewRecords = () => {
        // Navigate to the appropriate page based on what was imported
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

    if (!campaign) {
        return (
            <div className="p-8 text-center">
                <p className="text-muted-foreground">Carregando informações da campanha...</p>
            </div>
        );
    }

    return (
        <div className="space-y-8 max-w-4xl mx-auto">
            {/* Header */}
            <div className="space-y-2">
                <div className="flex items-center gap-2 text-muted-foreground">
                    <FolderOpen className="h-5 w-5" />
                    <h1 className="text-3xl font-bold text-foreground">Importar Prestação de Contas</h1>
                </div>
                <p className="text-muted-foreground">
                    Importe dados completos de uma prestação de contas do TSE para o ELEITORA
                </p>
            </div>

            {/* Step Indicator */}
            <div className="flex items-center justify-between">
                {[1, 2, 3, 4].map((s) => (
                    <div key={s} className="flex items-center">
                        <div
                            className={`flex items-center justify-center w-10 h-10 rounded-full font-medium ${
                                s <= step
                                    ? s === step
                                        ? 'bg-primary text-primary-foreground'
                                        : 'bg-green-600 text-white'
                                    : 'bg-muted text-muted-foreground'
                            }`}
                        >
                            {s < step ? '✓' : s}
                        </div>
                        {s < 4 && (
                            <div
                                className={`h-1 w-16 mx-2 ${
                                    s < step ? 'bg-green-600' : 'bg-muted'
                                }`}
                            />
                        )}
                    </div>
                ))}
            </div>

            {/* Step Labels */}
            <div className="grid grid-cols-4 gap-4 text-center text-xs font-medium">
                <div className={step >= 1 ? 'text-foreground' : 'text-muted-foreground'}>
                    Selecionar Pasta
                </div>
                <div className={step >= 2 ? 'text-foreground' : 'text-muted-foreground'}>
                    Validar
                </div>
                <div className={step >= 3 ? 'text-foreground' : 'text-muted-foreground'}>
                    Visualizar
                </div>
                <div className={step >= 4 ? 'text-foreground' : 'text-muted-foreground'}>
                    Importar
                </div>
            </div>

            {/* Content */}
            <div className="bg-card rounded-lg border border-border p-8">
                {step === 1 && (
                    <div className="space-y-6">
                        <div>
                            <h2 className="text-xl font-semibold mb-2 text-foreground">
                                Selecione a Pasta TSE
                            </h2>
                            <p className="text-muted-foreground mb-4">
                                Especifique o caminho da pasta que contém a prestação de contas do TSE
                            </p>
                        </div>

                        <TaxFileUploadZone
                            onFolderSelected={handleFolderSelected}
                            isLoading={isLoading}
                        />

                        {folderPath && (
                            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                                <p className="text-sm text-blue-800">
                                    Pasta selecionada: {folderPath}
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {step === 2 && (
                    <div className="space-y-6">
                        <div>
                            <h2 className="text-xl font-semibold mb-2 text-foreground">
                                Validar Estrutura
                            </h2>
                            <p className="text-muted-foreground">
                                Validando a estrutura da pasta TSE...
                            </p>
                        </div>

                        {validation && (
                            <div>
                                {validation.valid ? (
                                    <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                                        <p className="text-sm font-medium text-green-900 mb-2">
                                            ✓ Validação Bem-Sucedida
                                        </p>
                                        <p className="text-sm text-green-800">
                                            A pasta contém todos os arquivos necessários para importação.
                                        </p>
                                    </div>
                                ) : (
                                    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                                        <p className="text-sm font-medium text-red-900 mb-2">
                                            Erros de Validação:
                                        </p>
                                        <ul className="space-y-1">
                                            {(validation.errors || validationErrors).map((error, idx) => (
                                                <li key={idx} className="text-sm text-red-800">
                                                    • {error}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        )}

                        <div>
                            <p className="text-sm font-medium text-foreground mb-2">
                                Estrutura Esperada:
                            </p>
                            <ul className="text-sm text-muted-foreground space-y-1 font-mono">
                                <li>├── dados.info</li>
                                <li>├── RECEITAS/</li>
                                <li>├── DESPESAS/</li>
                                <li>├── EXTRATOS_BANCARIOS/</li>
                                <li>├── REPRESENTANTES/</li>
                                <li>└── [Other folders...]</li>
                            </ul>
                        </div>
                    </div>
                )}

                {step === 3 && preview && (
                    <div className="space-y-6">
                        <div>
                            <h2 className="text-xl font-semibold mb-2 text-foreground">
                                Visualizar Importação
                            </h2>
                            <p className="text-muted-foreground">
                                Verifique os dados que serão importados
                            </p>
                        </div>

                        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                            <div className="bg-muted/50 rounded-lg p-4 border border-border">
                                <p className="text-2xl font-bold text-primary">
                                    {preview.receitas_count || 0}
                                </p>
                                <p className="text-xs text-muted-foreground mt-1">Receitas</p>
                            </div>
                            <div className="bg-muted/50 rounded-lg p-4 border border-border">
                                <p className="text-2xl font-bold text-primary">
                                    {preview.despesas_count || 0}
                                </p>
                                <p className="text-xs text-muted-foreground mt-1">Despesas</p>
                            </div>
                            <div className="bg-muted/50 rounded-lg p-4 border border-border">
                                <p className="text-2xl font-bold text-primary">
                                    {preview.banco_count || 0}
                                </p>
                                <p className="text-xs text-muted-foreground mt-1">Extratos</p>
                            </div>
                            <div className="bg-muted/50 rounded-lg p-4 border border-border">
                                <p className="text-2xl font-bold text-primary">
                                    {preview.representantes ? Object.keys(preview.representantes).length : 0}
                                </p>
                                <p className="text-xs text-muted-foreground mt-1">Representantes</p>
                            </div>
                        </div>

                        {preview.receitas_sample && preview.receitas_sample.length > 0 && (
                            <div>
                                <p className="text-sm font-medium text-foreground mb-2">Amostra de Receitas:</p>
                                <div className="bg-muted/30 rounded-md p-3 space-y-1">
                                    {preview.receitas_sample.map((file, idx) => (
                                        <p key={idx} className="text-xs text-muted-foreground font-mono">
                                            {file}
                                        </p>
                                    ))}
                                </div>
                            </div>
                        )}

                        {preview.despesas_sample && preview.despesas_sample.length > 0 && (
                            <div>
                                <p className="text-sm font-medium text-foreground mb-2">Amostra de Despesas:</p>
                                <div className="bg-muted/30 rounded-md p-3 space-y-1">
                                    {preview.despesas_sample.map((file, idx) => (
                                        <p key={idx} className="text-xs text-muted-foreground font-mono">
                                            {file}
                                        </p>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {step === 4 && (
                    <div className="space-y-6">
                        {isImporting ? (
                            <>
                                <div>
                                    <h2 className="text-xl font-semibold mb-2 text-foreground">
                                        Importando Dados...
                                    </h2>
                                </div>
                                <ImportProgressBar
                                    isImporting={isImporting}
                                    currentStep={currentStep}
                                />
                            </>
                        ) : importSummary ? (
                            <>
                                <div>
                                    <h2 className="text-xl font-semibold mb-2 text-foreground">
                                        Resultado da Importação
                                    </h2>
                                </div>
                                <ImportSummary
                                    summary={importSummary}
                                    onClose={handleClose}
                                    onViewRecords={handleViewRecords}
                                />
                            </>
                        ) : null}
                    </div>
                )}
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 flex-wrap">
                {step > 1 && step < 4 && (
                    <Button
                        variant="outline"
                        onClick={() => setStep(step - 1)}
                        disabled={isLoading}
                    >
                        <ChevronLeft className="h-4 w-4 mr-2" />
                        Voltar
                    </Button>
                )}

                {step === 1 && (
                    <Button
                        onClick={handleValidate}
                        disabled={!folderPath || isLoading}
                        className="ml-auto"
                    >
                        Próximo
                        <ChevronRight className="h-4 w-4 ml-2" />
                    </Button>
                )}

                {step === 2 && validation && validation.valid && (
                    <Button
                        onClick={handlePreview}
                        disabled={isLoading}
                        className="ml-auto"
                    >
                        Visualizar
                        <ChevronRight className="h-4 w-4 ml-2" />
                    </Button>
                )}

                {step === 3 && preview && (
                    <Button
                        onClick={handleExecuteImport}
                        disabled={isImporting}
                        className="ml-auto bg-green-600 hover:bg-green-700"
                    >
                        Importar Agora
                        <ChevronRight className="h-4 w-4 ml-2" />
                    </Button>
                )}

                {step === 4 && importSummary && !isImporting && (
                    <Button
                        variant="outline"
                        onClick={handleClose}
                        className="ml-auto"
                    >
                        Fechar
                    </Button>
                )}
            </div>
        </div>
    );
}
