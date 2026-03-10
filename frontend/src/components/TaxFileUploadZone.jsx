import { useState, useRef } from 'react';
import { Upload, X, FileArchive } from 'lucide-react';
import { Button } from './ui/button';
import { toast } from 'sonner';

export function TaxFileUploadZone({ onFileSelected, isLoading }) {
    const [dragActive, setDragActive] = useState(false);
    const [selectedFile, setSelectedFile] = useState(null);
    const fileInputRef = useRef(null);

    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const validateFile = (file) => {
        const validExtensions = ['.zip', '.rar', '.7z'];
        const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

        if (!validExtensions.includes(fileExtension)) {
            toast.error('Tipos aceitos: ZIP, RAR ou 7Z');
            return false;
        }

        // Max 500MB
        if (file.size > 500 * 1024 * 1024) {
            toast.error('Arquivo muito grande (máx 500MB)');
            return false;
        }

        return true;
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);

        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            const file = files[0];
            if (validateFile(file)) {
                setSelectedFile(file);
                onFileSelected(file);
                toast.success(`Arquivo selecionado: ${file.name}`);
            }
        }
    };

    const handleChange = (e) => {
        const files = e.target.files;
        if (files && files.length > 0) {
            const file = files[0];
            if (validateFile(file)) {
                setSelectedFile(file);
                onFileSelected(file);
                toast.success(`Arquivo selecionado: ${file.name}`);
            }
        }
    };

    const handleClick = () => {
        fileInputRef.current?.click();
    };

    const clearFile = () => {
        setSelectedFile(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = '';
        }
    };

    return (
        <div className="w-full space-y-4">
            {/* Drag & Drop Area */}
            <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={handleClick}
                className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer ${
                    dragActive
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/50 hover:bg-muted/30'
                }`}
            >
                <Upload className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
                <p className="text-lg font-medium mb-2">Selecione o arquivo TSE</p>
                <p className="text-sm text-muted-foreground mb-4">
                    Clique para escolher ou arraste e solte o arquivo aqui
                </p>
                <p className="text-xs text-muted-foreground">
                    Formatos aceitos: ZIP, RAR, 7Z (máx 500MB)
                </p>
                <input
                    ref={fileInputRef}
                    type="file"
                    onChange={handleChange}
                    disabled={isLoading}
                    accept=".zip,.rar,.7z"
                    className="hidden"
                />
            </div>

            {/* Selected File Display */}
            {selectedFile && (
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
                            variant="ghost"
                            size="icon"
                            onClick={clearFile}
                            disabled={isLoading}
                            className="text-blue-600 hover:text-blue-700"
                        >
                            <X className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            )}

            {/* Instructions */}
            <div className="bg-muted/50 rounded-md p-4 border border-border">
                <p className="text-sm font-medium mb-2 text-foreground">Como funciona:</p>
                <ul className="text-xs space-y-1 text-muted-foreground">
                    <li>✓ Faça download da prestação de contas do portal TSE</li>
                    <li>✓ O arquivo virá em ZIP ou RAR com a pasta ATSEPJE_XXXXX</li>
                    <li>✓ Selecione o arquivo ZIP/RAR aqui ou arraste para esta área</li>
                    <li>✓ O sistema irá descompactar e processar automaticamente</li>
                </ul>
            </div>
        </div>
    );
}
