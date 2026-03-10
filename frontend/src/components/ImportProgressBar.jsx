import { useEffect, useState } from 'react';
import { Progress } from './ui/progress';
import { Loader2 } from 'lucide-react';

export function ImportProgressBar({ isImporting, progress = 0, currentStep = '', totalSteps = 5 }) {
    const [displayProgress, setDisplayProgress] = useState(0);

    useEffect(() => {
        if (isImporting) {
            // Smooth animation of progress
            const timer = setTimeout(() => {
                setDisplayProgress(Math.min(progress, 100));
            }, 100);
            return () => clearTimeout(timer);
        } else {
            setDisplayProgress(0);
        }
    }, [progress, isImporting]);

    if (!isImporting) return null;

    const steps = [
        'Validando estrutura',
        'Carregando metadados',
        'Extraindo dados',
        'Importando para banco de dados',
        'Salvando anexos'
    ];

    const currentStepIndex = steps.indexOf(currentStep) || 0;
    const overallProgress = ((currentStepIndex + displayProgress / 100) / steps.length) * 100;

    return (
        <div className="space-y-4 w-full">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                    <div>
                        <p className="text-sm font-medium text-foreground">
                            Importando prestação de contas...
                        </p>
                        <p className="text-xs text-muted-foreground">
                            {currentStep || 'Iniciando importação...'}
                        </p>
                    </div>
                </div>
                <span className="text-sm font-medium text-muted-foreground">
                    {Math.round(overallProgress)}%
                </span>
            </div>

            {/* Main Progress Bar */}
            <Progress value={overallProgress} className="h-2" />

            {/* Step Indicators */}
            <div className="grid grid-cols-5 gap-2">
                {steps.map((step, index) => (
                    <div key={index} className="space-y-1">
                        <div
                            className={`h-1 rounded-full transition-colors ${
                                index < currentStepIndex
                                    ? 'bg-green-500'
                                    : index === currentStepIndex
                                    ? 'bg-blue-500'
                                    : 'bg-gray-200'
                            }`}
                        />
                        <p
                            className={`text-xs text-center ${
                                index <= currentStepIndex
                                    ? 'text-foreground font-medium'
                                    : 'text-muted-foreground'
                            }`}
                        >
                            {index + 1}
                        </p>
                    </div>
                ))}
            </div>

            {/* Step Details */}
            <div className="bg-muted/50 rounded-md p-3 border border-border">
                <p className="text-xs font-medium text-foreground mb-2">Progresso:</p>
                <div className="space-y-1">
                    {steps.map((step, index) => (
                        <div
                            key={index}
                            className={`text-xs ${
                                index < currentStepIndex
                                    ? 'text-green-600'
                                    : index === currentStepIndex
                                    ? 'text-blue-600 font-medium'
                                    : 'text-muted-foreground'
                            }`}
                        >
                            <span className="mr-2">
                                {index < currentStepIndex ? '✓' : index === currentStepIndex ? '⟳' : '○'}
                            </span>
                            {step}
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
