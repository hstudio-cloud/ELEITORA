import { CheckCircle2, AlertCircle, XCircle } from 'lucide-react';
import { Button } from './ui/button';

export function ImportSummary({ summary, onClose, onViewRecords }) {
    if (!summary) return null;

    const hasErrors = summary.errors && summary.errors.length > 0;
    const totalCreated =
        (summary.receitas_created || 0) +
        (summary.despesas_created || 0) +
        (summary.banco_created || 0) +
        (summary.files_saved || 0);

    return (
        <div className="space-y-6 w-full">
            {/* Header */}
            <div className="space-y-2">
                <div className="flex items-center gap-3">
                    {hasErrors ? (
                        <AlertCircle className="h-6 w-6 text-amber-600" />
                    ) : (
                        <CheckCircle2 className="h-6 w-6 text-green-600" />
                    )}
                    <h3 className="text-lg font-semibold text-foreground">
                        {hasErrors ? 'Importação Concluída com Avisos' : 'Importação Concluída com Sucesso!'}
                    </h3>
                </div>
                <p className="text-sm text-muted-foreground">
                    {summary.message || 'Os dados foram processados e armazenados'}
                </p>
            </div>

            {/* Statistics Grid */}
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                {/* Receitas */}
                <div className="bg-muted/50 rounded-lg p-4 border border-border">
                    <p className="text-2xl font-bold text-primary">
                        {summary.receitas_created || 0}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Receitas Importadas</p>
                </div>

                {/* Despesas */}
                <div className="bg-muted/50 rounded-lg p-4 border border-border">
                    <p className="text-2xl font-bold text-primary">
                        {summary.despesas_created || 0}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Despesas Importadas</p>
                </div>

                {/* Banco */}
                <div className="bg-muted/50 rounded-lg p-4 border border-border">
                    <p className="text-2xl font-bold text-primary">
                        {summary.banco_created || 0}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Extratos Bancários</p>
                </div>

                {/* Arquivos */}
                <div className="bg-muted/50 rounded-lg p-4 border border-border">
                    <p className="text-2xl font-bold text-primary">
                        {summary.files_saved || 0}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">Arquivos Salvos</p>
                </div>
            </div>

            {/* Errors Section */}
            {hasErrors && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                        <XCircle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
                        <div className="flex-1">
                            <h4 className="font-medium text-red-900 mb-2">Erros Encontrados:</h4>
                            <ul className="space-y-1">
                                {summary.errors.map((error, idx) => (
                                    <li key={idx} className="text-sm text-red-800">
                                        • {error}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                </div>
            )}

            {/* Success Message */}
            {!hasErrors && totalCreated > 0 && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                    <p className="text-sm text-green-800">
                        ✓ {totalCreated} registro(s) foram criados com sucesso e estão disponíveis no sistema.
                    </p>
                </div>
            )}

            {/* Empty Import Message */}
            {totalCreated === 0 && !hasErrors && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <p className="text-sm text-blue-800">
                        ℹ️ Nenhum registro foi criado. A pasta pode estar vazia ou os arquivos podem não estar no formato esperado.
                    </p>
                </div>
            )}

            {/* Details Section */}
            <div className="bg-muted/50 rounded-lg p-4 border border-border space-y-3">
                <h4 className="font-medium text-foreground text-sm">Detalhes da Importação:</h4>
                <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                        <span className="text-muted-foreground">Receitas Importadas:</span>
                        <span className="font-medium text-foreground">{summary.receitas_created || 0}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-muted-foreground">Despesas Importadas:</span>
                        <span className="font-medium text-foreground">{summary.despesas_created || 0}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-muted-foreground">Extratos Bancários:</span>
                        <span className="font-medium text-foreground">{summary.banco_created || 0}</span>
                    </div>
                    <div className="flex justify-between">
                        <span className="text-muted-foreground">Arquivos Salvos:</span>
                        <span className="font-medium text-foreground">{summary.files_saved || 0}</span>
                    </div>
                    {summary.total_amount_income > 0 && (
                        <div className="flex justify-between pt-2 border-t border-border">
                            <span className="text-muted-foreground">Total de Receitas:</span>
                            <span className="font-medium text-green-600">
                                R$ {summary.total_amount_income?.toLocaleString('pt-BR', {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2
                                })}
                            </span>
                        </div>
                    )}
                    {summary.total_amount_expenses > 0 && (
                        <div className="flex justify-between">
                            <span className="text-muted-foreground">Total de Despesas:</span>
                            <span className="font-medium text-red-600">
                                R$ {summary.total_amount_expenses?.toLocaleString('pt-BR', {
                                    minimumFractionDigits: 2,
                                    maximumFractionDigits: 2
                                })}
                            </span>
                        </div>
                    )}
                </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 pt-4 border-t border-border">
                {totalCreated > 0 && (
                    <Button
                        onClick={onViewRecords}
                        className="flex-1"
                    >
                        Ver Registros Importados
                    </Button>
                )}
                <Button
                    variant="outline"
                    onClick={onClose}
                    className="flex-1"
                >
                    Fechar
                </Button>
            </div>
        </div>
    );
}
