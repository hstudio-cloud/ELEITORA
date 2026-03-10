import { useState } from 'react';
import { Upload, X } from 'lucide-react';
import { Button } from './ui/button';
import { toast } from 'sonner';

export function TaxFileUploadZone({ onFolderSelected, isLoading }) {
    const [dragActive, setDragActive] = useState(false);
    const [selectedPath, setSelectedPath] = useState('');

    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);

        // Note: Due to browser security, we cannot access local file paths directly
        // User must manually enter the path or use the file input
        toast.info('Por favor, use o campo de entrada para especificar o caminho da pasta');
    };

    const handleChange = (e) => {
        const value = e.target.value;
        setSelectedPath(value);
        if (value.trim()) {
            onFolderSelected(value.trim());
        }
    };

    const clearPath = () => {
        setSelectedPath('');
    };

    return (
        <div className="w-full space-y-4">
            {/* Drag & Drop Area */}
            <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                    dragActive
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/50'
                }`}
            >
                <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-lg font-medium mb-2">Selecione a pasta TSE</p>
                <p className="text-sm text-muted-foreground mb-4">
                    Arraste a pasta aqui ou use o campo abaixo para especificar o caminho
                </p>
                <p className="text-xs text-muted-foreground">
                    Esperado: ATSEPJE_XXXXX/
                </p>
            </div>

            {/* Path Input */}
            <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                    Caminho da Pasta
                </label>
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={selectedPath}
                        onChange={handleChange}
                        disabled={isLoading}
                        placeholder="Ex: C:\Users\You\Desktop\ATSEPJE_000131116918RN4058977_PFR"
                        className="flex-1 px-3 py-2 border border-border rounded-md bg-background text-foreground placeholder-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-50"
                    />
                    {selectedPath && (
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={clearPath}
                            disabled={isLoading}
                        >
                            <X className="h-4 w-4" />
                        </Button>
                    )}
                </div>
                <p className="text-xs text-muted-foreground">
                    Digite o caminho completo da pasta que contém os arquivos TSE
                </p>
            </div>

            {/* Example Path */}
            <div className="bg-muted/50 rounded-md p-4 border border-border">
                <p className="text-sm font-medium mb-2 text-foreground">Exemplos de caminho:</p>
                <ul className="text-xs space-y-1 text-muted-foreground font-mono">
                    <li>• Windows: C:\Users\Seu Usuário\Desktop\ATSEPJE_000131116918RN4058977_PFR</li>
                    <li>• Mac/Linux: /home/usuario/Downloads/ATSEPJE_000131116918RN4058977_PFR</li>
                </ul>
            </div>

            {/* Status Message */}
            {selectedPath && (
                <div className="bg-blue-500/10 border border-blue-500/30 rounded-md p-3 text-sm text-blue-700">
                    Pasta selecionada ✓
                </div>
            )}
        </div>
    );
}
