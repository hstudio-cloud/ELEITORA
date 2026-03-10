import { useState, useRef } from 'react';
import { Upload } from 'lucide-react';

export function TaxFileUploadZone({ onFileSelected, isLoading }) {
    const [dragActive, setDragActive] = useState(false);
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

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);

        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            const file = files[0];
            onFileSelected(file);
        }
    };

    const handleChange = (e) => {
        const files = e.target.files;
        if (files && files.length > 0) {
            const file = files[0];
            onFileSelected(file);
        }
    };

    const handleClick = () => {
        fileInputRef.current?.click();
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
                    Formato: ZIP ou RAR (máx 500MB)
                </p>
                <input
                    ref={fileInputRef}
                    type="file"
                    onChange={handleChange}
                    disabled={isLoading}
                    className="hidden"
                />
            </div>

            {/* Instructions */}
            <div className="bg-muted/50 rounded-md p-4 border border-border">
                <p className="text-sm font-medium mb-2 text-foreground">Como funciona:</p>
                <ul className="text-xs space-y-1 text-muted-foreground">
                    <li>✓ Download da prestação de contas do portal TSE</li>
                    <li>✓ Arquivo virá em ZIP ou RAR com pasta ATSEPJE_XXXXX</li>
                    <li>✓ Selecione o arquivo ou arraste para esta área</li>
                    <li>✓ Sistema descompactará e processará automaticamente</li>
                </ul>
            </div>
        </div>
    );
}
