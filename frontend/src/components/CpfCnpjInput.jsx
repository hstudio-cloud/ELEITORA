import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Input } from '../components/ui/input';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Local validation functions
const validateCPFLocal = (cpf) => {
    cpf = cpf.replace(/[^\d]/g, '');
    if (cpf.length !== 11) return false;
    if (/^(\d)\1+$/.test(cpf)) return false;
    
    let sum = 0;
    for (let i = 0; i < 9; i++) {
        sum += parseInt(cpf.charAt(i)) * (10 - i);
    }
    let digit1 = 11 - (sum % 11);
    if (digit1 > 9) digit1 = 0;
    if (parseInt(cpf.charAt(9)) !== digit1) return false;
    
    sum = 0;
    for (let i = 0; i < 10; i++) {
        sum += parseInt(cpf.charAt(i)) * (11 - i);
    }
    let digit2 = 11 - (sum % 11);
    if (digit2 > 9) digit2 = 0;
    
    return parseInt(cpf.charAt(10)) === digit2;
};

const validateCNPJLocal = (cnpj) => {
    cnpj = cnpj.replace(/[^\d]/g, '');
    if (cnpj.length !== 14) return false;
    if (/^(\d)\1+$/.test(cnpj)) return false;
    
    const weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    
    let sum = 0;
    for (let i = 0; i < 12; i++) {
        sum += parseInt(cnpj.charAt(i)) * weights1[i];
    }
    let digit1 = sum % 11;
    digit1 = digit1 < 2 ? 0 : 11 - digit1;
    if (parseInt(cnpj.charAt(12)) !== digit1) return false;
    
    sum = 0;
    for (let i = 0; i < 13; i++) {
        sum += parseInt(cnpj.charAt(i)) * weights2[i];
    }
    let digit2 = sum % 11;
    digit2 = digit2 < 2 ? 0 : 11 - digit2;
    
    return parseInt(cnpj.charAt(13)) === digit2;
};

const formatCPF = (cpf) => {
    cpf = cpf.replace(/[^\d]/g, '');
    if (cpf.length <= 3) return cpf;
    if (cpf.length <= 6) return `${cpf.slice(0, 3)}.${cpf.slice(3)}`;
    if (cpf.length <= 9) return `${cpf.slice(0, 3)}.${cpf.slice(3, 6)}.${cpf.slice(6)}`;
    return `${cpf.slice(0, 3)}.${cpf.slice(3, 6)}.${cpf.slice(6, 9)}-${cpf.slice(9, 11)}`;
};

const formatCNPJ = (cnpj) => {
    cnpj = cnpj.replace(/[^\d]/g, '');
    if (cnpj.length <= 2) return cnpj;
    if (cnpj.length <= 5) return `${cnpj.slice(0, 2)}.${cnpj.slice(2)}`;
    if (cnpj.length <= 8) return `${cnpj.slice(0, 2)}.${cnpj.slice(2, 5)}.${cnpj.slice(5)}`;
    if (cnpj.length <= 12) return `${cnpj.slice(0, 2)}.${cnpj.slice(2, 5)}.${cnpj.slice(5, 8)}/${cnpj.slice(8)}`;
    return `${cnpj.slice(0, 2)}.${cnpj.slice(2, 5)}.${cnpj.slice(5, 8)}/${cnpj.slice(8, 12)}-${cnpj.slice(12, 14)}`;
};

const formatDocument = (value) => {
    const digits = value.replace(/[^\d]/g, '');
    if (digits.length <= 11) {
        return formatCPF(digits);
    }
    return formatCNPJ(digits);
};

export function CpfCnpjInput({ 
    value, 
    onChange, 
    onValidationChange,
    placeholder = "CPF ou CNPJ",
    className,
    ...props 
}) {
    const [displayValue, setDisplayValue] = useState('');
    const [isValid, setIsValid] = useState(null);
    const [validating, setValidating] = useState(false);
    const [docType, setDocType] = useState(null);

    // Format and validate on value change
    useEffect(() => {
        if (value) {
            setDisplayValue(formatDocument(value));
        } else {
            setDisplayValue('');
            setIsValid(null);
            setDocType(null);
        }
    }, [value]);

    const validateDocument = useCallback((rawValue) => {
        const digits = rawValue.replace(/[^\d]/g, '');
        
        if (digits.length === 0) {
            setIsValid(null);
            setDocType(null);
            onValidationChange?.(null, null);
            return;
        }

        if (digits.length === 11) {
            const valid = validateCPFLocal(digits);
            setIsValid(valid);
            setDocType('cpf');
            onValidationChange?.(valid, 'cpf');
        } else if (digits.length === 14) {
            const valid = validateCNPJLocal(digits);
            setIsValid(valid);
            setDocType('cnpj');
            onValidationChange?.(valid, 'cnpj');
        } else if (digits.length < 11) {
            setIsValid(null);
            setDocType('cpf');
            onValidationChange?.(null, 'cpf');
        } else {
            setIsValid(null);
            setDocType('cnpj');
            onValidationChange?.(null, 'cnpj');
        }
    }, [onValidationChange]);

    const handleChange = (e) => {
        let rawValue = e.target.value;
        const digits = rawValue.replace(/[^\d]/g, '');
        
        // Limit length
        if (digits.length > 14) return;
        
        const formatted = formatDocument(digits);
        setDisplayValue(formatted);
        onChange?.(digits);
        
        // Validate
        validateDocument(digits);
    };

    return (
        <div className="relative">
            <Input
                value={displayValue}
                onChange={handleChange}
                placeholder={placeholder}
                className={cn(
                    "pr-10",
                    isValid === true && "border-green-500 focus-visible:ring-green-500",
                    isValid === false && "border-red-500 focus-visible:ring-red-500",
                    className
                )}
                {...props}
            />
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
                {validating && (
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                )}
                {!validating && isValid === true && (
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                )}
                {!validating && isValid === false && (
                    <XCircle className="h-4 w-4 text-red-500" />
                )}
            </div>
            {docType && displayValue && (
                <p className={cn(
                    "text-xs mt-1",
                    isValid === true && "text-green-500",
                    isValid === false && "text-red-500",
                    isValid === null && "text-muted-foreground"
                )}>
                    {docType === 'cpf' ? 'CPF' : 'CNPJ'}
                    {isValid === true && ' válido'}
                    {isValid === false && ' inválido'}
                </p>
            )}
        </div>
    );
}

// Hook for CPF/CNPJ validation
export function useCpfCnpjValidation() {
    const [isValid, setIsValid] = useState(null);
    const [docType, setDocType] = useState(null);
    const [formatted, setFormatted] = useState('');

    const validate = useCallback((value) => {
        if (!value) {
            setIsValid(null);
            setDocType(null);
            setFormatted('');
            return { isValid: null, docType: null, formatted: '' };
        }

        const digits = value.replace(/[^\d]/g, '');
        let valid = null;
        let type = null;

        if (digits.length === 11) {
            valid = validateCPFLocal(digits);
            type = 'cpf';
        } else if (digits.length === 14) {
            valid = validateCNPJLocal(digits);
            type = 'cnpj';
        }

        const fmt = formatDocument(digits);
        
        setIsValid(valid);
        setDocType(type);
        setFormatted(fmt);

        return { isValid: valid, docType: type, formatted: fmt };
    }, []);

    return { isValid, docType, formatted, validate };
}

export default CpfCnpjInput;
