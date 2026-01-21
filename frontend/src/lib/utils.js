import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
    return twMerge(clsx(inputs));
}

export function formatCurrency(value) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(value || 0);
}

export function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('pt-BR').format(date);
}

export function formatDateInput(dateString) {
    if (!dateString) return '';
    return dateString.split('T')[0];
}

export const categoryLabels = {
    // Revenue categories
    doacao_pf: 'Doação Pessoa Física',
    doacao_pj: 'Doação Pessoa Jurídica',
    recursos_proprios: 'Recursos Próprios',
    fundo_eleitoral: 'Fundo Eleitoral',
    fundo_partidario: 'Fundo Partidário',
    outros: 'Outros',
    // Expense categories
    publicidade: 'Publicidade',
    material_grafico: 'Material Gráfico',
    servicos_terceiros: 'Serviços de Terceiros',
    transporte: 'Transporte',
    alimentacao: 'Alimentação',
    pessoal: 'Pessoal',
    eventos: 'Eventos'
};

export const statusLabels = {
    rascunho: 'Rascunho',
    ativo: 'Ativo',
    concluido: 'Concluído',
    cancelado: 'Cancelado',
    pendente: 'Pendente',
    pago: 'Pago'
};

export const statusColors = {
    rascunho: 'bg-muted text-muted-foreground',
    ativo: 'bg-secondary/20 text-secondary',
    concluido: 'bg-primary/20 text-primary',
    cancelado: 'bg-destructive/20 text-destructive',
    pendente: 'bg-accent/20 text-accent',
    pago: 'bg-secondary/20 text-secondary'
};
