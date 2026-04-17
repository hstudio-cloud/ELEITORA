import { useState, useEffect, useRef } from 'react';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import axios from 'axios';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { formatCurrency } from '../lib/utils';
import { 
    Bot, Send, Loader2, Trash2, AlertTriangle, 
    FileText, BarChart3, Shield, Sparkles,
    Mic, Volume2, VolumeX,
    Radio
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

// Quick action buttons
const quickActions = [
    { label: 'Resumo financeiro', prompt: 'Qual é o resumo financeiro da minha campanha?', icon: BarChart3 },
    { label: 'Verificar conformidade', prompt: 'Minha campanha está em conformidade com as regras do TSE?', icon: Shield },
    { label: 'Analisar despesas', prompt: 'Analise minhas despesas e sugira otimizações', icon: FileText },
    { label: 'Documentos pendentes', prompt: 'Quais documentos estão pendentes nos meus contratos?', icon: AlertTriangle },
];

// Voice commands examples
const voiceExamples = [
    'Flora, qual é meu saldo?',
    'Flora, tenho alguma despesa para registrar?',
    'Flora, tem contrato para finalizar?',
    'Flora, quais pagamentos vencem esta semana?',
    'Adicionar despesa de 500 reais em publicidade',
    'Mostrar contratos pendentes'
];

export default function Assistente() {
    const navigate = useNavigate();
    const { user } = useAuth();
    const perfil = String(user?.role || '').toLowerCase().includes('contador') ? 'contador' : 'candidato';
    const [messages, setMessages] = useState([]);
    const [inputMessage, setInputMessage] = useState('');
    const [loading, setLoading] = useState(false);
    const [loadingHistory, setLoadingHistory] = useState(true);
    const [alerts, setAlerts] = useState([]);
    const [sessionId, setSessionId] = useState(null);
    const [proactiveSummary, setProactiveSummary] = useState(null);
    const [hasSeenTour, setHasSeenTour] = useState(false);
    const [tourShown, setTourShown] = useState(false);
    const scrollRef = useRef(null);
    const inputRef = useRef(null);

    // Voice state
    const [isProcessingVoice, setIsProcessingVoice] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [voiceEnabled, setVoiceEnabled] = useState(true);
    const [wakeEnabled] = useState(true);
    const [wakePermission, setWakePermission] = useState('unknown');
    const [wakeSupported, setWakeSupported] = useState(false);
    const [wakeStatus, setWakeStatus] = useState('inativo');
    const [manualListening, setManualListening] = useState(false);
    const [wakePhrase, setWakePhrase] = useState('');
    const [lastTranscription, setLastTranscription] = useState('');
    const audioRef = useRef(null);
    const recognitionRef = useRef(null);
    const manualRecognitionRef = useRef(null);
    const wakeCooldownRef = useRef(0);
    const wakePendingRef = useRef(false);
    const wakeTimeoutRef = useRef(null);

    useEffect(() => {
        fetchChatHistory();
        checkTourStatus();
        fetchProactiveSummary();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        setWakeSupported(Boolean(SpeechRecognition));
    }, []);

    useEffect(() => {
        if (!wakeSupported) return;
        requestMicrophoneAccess();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [wakeSupported]);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    // Check if user has completed the tour
    const checkTourStatus = () => {
        const tourKey = `flora_tour_completed_${user?.id || 'anon'}`;
        const completed = localStorage.getItem(tourKey) === '1';
        setHasSeenTour(completed);
    };

    // Show tour message only on first access
    const showTourIfNeeded = () => {
        if (!hasSeenTour && !tourShown) {
            const tourKey = `flora_tour_completed_${user?.id || 'anon'}`;
            localStorage.setItem(tourKey, '1');
            setTourShown(true);

            const role = String(user?.role || '').toLowerCase();
            const perfil = role.includes('contador') ? 'contador' : 'candidato';
            const tourMessage = {
                role: 'assistant',
                content: `Ola ${perfil}, em que posso te ajudar hoje?`,
                timestamp: new Date().toISOString(),
                isTour: true
            };
            setMessages([tourMessage]);
            if (voiceEnabled) {
                speakText(tourMessage.content);
            }
        }
    };

    useEffect(() => {
        if (messages.length === 0 && hasSeenTour !== null && !tourShown) {
            showTourIfNeeded();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [hasSeenTour]);

    const fetchChatHistory = async () => {
        try {
            const response = await axios.get(`${API}/ai/chat/history`);
            setMessages(response.data.messages || []);
            setSessionId(response.data.session_id);
        } catch (error) {
            console.error('Erro ao carregar histórico:', error);
        } finally {
            setLoadingHistory(false);
        }
    };

    // Generate intelligent contextual questions based on campaign state
    const generateContextualQuestions = (summary) => {
        const questions = [];
        const hour = new Date().getHours();
        const isBusinessHours = hour >= 9 && hour < 18;

        // Morning greeting
        if (hour < 12) {
            questions.push('Qual é o cenário financeiro da campanha hoje?');
        } else if (hour >= 12 && hour < 15) {
            questions.push('Teve alguma despesa nova a registrar nesta tarde?');
        } else {
            questions.push('Como foi o dia financeiro da campanha?');
        }

        // If there are pending expenses
        if (summary.pendingExpensesCount > 0) {
            if (summary.pendingExpensesCount === 1) {
                questions.push('Tenho 1 despesa pendente. Me ajuda a registrá-la?');
            } else {
                questions.push(`Tenho ${summary.pendingExpensesCount} despesas para registrar. Quer me ajudar?`);
            }
        }

        // If there are contracts to sign
        if (summary.unsignedContractsCount > 0) {
            questions.push(`Tenho ${summary.unsignedContractsCount} contrato(s) para assinar. Pode gerar o link?`);
        }

        // If there are due payments
        if (summary.dueSoonCount > 0) {
            questions.push(`Tenho ${summary.dueSoonCount} pagamento(s) vencendo em breve. Me lembra dos valores?`);
        }

        // Compliance check (once a week)
        const weekCheck = Math.floor(Math.random() * 7) === 0;
        if (weekCheck) {
            questions.push('Minha campanha está em conformidade com as regras do TSE?');
        }

        return questions;
    };

    const fetchProactiveSummary = async () => {
        try {
            const [statsRes, paymentsRes, contractsRes, expensesRes] = await Promise.all([
                axios.get(`${API}/dashboard/stats`).catch(() => ({ data: {} })),
                axios.get(`${API}/payments/alerts?days_ahead=7`).catch(() => ({ data: { alerts: [], total: 0 } })),
                axios.get(`${API}/contracts`).catch(() => ({ data: [] })),
                axios.get(`${API}/expenses`).catch(() => ({ data: [] }))
            ]);

            const contracts = contractsRes.data || [];
            const expenses = expensesRes.data || [];
            const pendingExpenses = expenses.filter(e => (e.payment_status || '').toLowerCase() !== 'pago');
            const dueSoonCount = (paymentsRes.data?.alerts || []).length || 0;
            const unsignedContracts = contracts.filter(c => !['assinado', 'concluido', 'finalizado'].includes((c.status || '').toLowerCase()));

            const summary = {
                pendingExpensesCount: pendingExpenses.length,
                pendingExpensesValue: pendingExpenses.reduce((sum, e) => sum + Number(e.amount || 0), 0),
                dueSoonCount,
                unsignedContractsCount: unsignedContracts.length,
                activeContractsCount: Number(statsRes.data?.active_contracts || 0),
                totalBalance: Number(statsRes.data?.balance || 0),
                totalRevenue: Number(statsRes.data?.revenue || 0),
                totalExpenses: Number(statsRes.data?.expenses || 0)
            };
            setProactiveSummary(summary);

            // Show proactive message only once per day (after tour)
            const todayKey = `flora_proactive_${user?.id || 'anon'}_${new Date().toISOString().slice(0, 10)}`;
            const alreadyPrompted = localStorage.getItem(todayKey) === '1';

            if (!alreadyPrompted && hasSeenTour) {
                const role = String(user?.role || '').toLowerCase().includes('contador') ? 'contador' : 'candidato';

                // Generate contextual questions
                const contextualQuestions = generateContextualQuestions(summary);
                const randomQuestion = contextualQuestions[Math.floor(Math.random() * contextualQuestions.length)];

                // Build smart greeting
                let greeting = `Oi, ${role}! `;

                if (summary.pendingExpensesCount > 0 || summary.dueSoonCount > 0 || summary.unsignedContractsCount > 0) {
                    greeting += 'Tenho um resumo rápido:\n';
                    if (summary.pendingExpensesCount > 0) {
                        greeting += `${summary.pendingExpensesCount} despesa(s) pendente(s) (R$ ${summary.pendingExpensesValue.toFixed(2)})\n`;
                    }
                    if (summary.dueSoonCount > 0) {
                        greeting += `${summary.dueSoonCount} pagamento(s) vencendo em 7 dias\n`;
                    }
                    if (summary.unsignedContractsCount > 0) {
                        greeting += `${summary.unsignedContractsCount} contrato(s) para finalizar\n`;
                    }
                    greeting += `\n${randomQuestion}`;
                } else {
                    greeting += `Sua campanha está em ordem! ${randomQuestion}`;
                }

                const proactiveMessage = {
                    role: 'assistant',
                    content: greeting,
                    timestamp: new Date().toISOString(),
                    isVoice: true,
                    isProactive: true
                };

                if (messages.length === 0 || !messages[0].isTour) {
                    setMessages(prev => (prev.length === 0 ? [proactiveMessage] : prev));
                }

                if (voiceEnabled) {
                    speakText(greeting);
                }
                localStorage.setItem(todayKey, '1');
            }
        } catch (error) {
            console.error('Erro ao carregar resumo proativo da Flora:', error);
        }
    };

    const sendMessage = async (messageText = null) => {
        const text = messageText || inputMessage.trim();
        if (!text) return;

        const userMessage = {
            role: 'user',
            content: text,
            timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, userMessage]);
        setInputMessage('');
        setLoading(true);

        try {
            const response = await axios.post(`${API}/ai/chat`, {
                message: text,
                session_id: sessionId
            });

            const assistantMessage = {
                role: 'assistant',
                content: response.data.response,
                timestamp: new Date().toISOString()
            };
            setMessages(prev => [...prev, assistantMessage]);
            
            if (response.data.alerts) {
                setAlerts(response.data.alerts);
            }
            if (response.data.session_id) {
                setSessionId(response.data.session_id);
            }
            
            // Speak response if voice is enabled
            if (voiceEnabled) {
                speakText(response.data.response);
            }
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao enviar mensagem');
            setMessages(prev => prev.slice(0, -1));
        } finally {
            setLoading(false);
            inputRef.current?.focus();
        }
    };

    const clearHistory = async () => {
        if (!window.confirm('Tem certeza que deseja limpar o histórico de conversas?')) return;
        
        try {
            await axios.delete(`${API}/ai/chat/history`);
            setMessages([]);
            toast.success('Histórico limpo');
        } catch (error) {
            toast.error('Erro ao limpar histórico');
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    // ============== Voice Functions ==============

const handleVoiceAction = (action, data) => {
        switch (action) {
            case 'navigate':
                toast.success(`Navegando para ${data.route}`);
                setTimeout(() => navigate(data.route), 1500);
                break;
            case 'expense_added':
                toast.success(`Despesa de R$ ${data.amount} adicionada!`);
                break;
            case 'revenue_added':
                toast.success(`Receita de R$ ${data.amount} adicionada!`);
                break;
            default:
                break;
        }
    };

    const playAudioResponse = (base64Audio) => {
        try {
            setIsSpeaking(true);
            const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
            audioRef.current = audio;
            
            audio.onended = () => {
                setIsSpeaking(false);
            };
            
            audio.onerror = () => {
                setIsSpeaking(false);
                console.error('Error playing audio');
            };
            
            audio.play();
        } catch (error) {
            setIsSpeaking(false);
            console.error('Error playing audio:', error);
        }
    };

    const stopSpeaking = () => {
        if (audioRef.current) {
            audioRef.current.pause();
            audioRef.current.currentTime = 0;
            setIsSpeaking(false);
        }
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
        }
    };

    const speakWithBrowserVoice = (text) => {
        if (!('speechSynthesis' in window)) return;
        try {
            const utterance = new SpeechSynthesisUtterance(text.substring(0, 500));
            const voices = window.speechSynthesis.getVoices();
            const preferredVoice =
                voices.find(v => /pt-BR/i.test(v.lang) && /luciana|maria|francisca|google|microsoft|female|mulher/i.test(v.name)) ||
                voices.find(v => /pt-BR/i.test(v.lang)) ||
                voices[0];
            if (preferredVoice) utterance.voice = preferredVoice;
            utterance.lang = 'pt-BR';
            utterance.rate = 0.95;
            utterance.pitch = 1.05;
            utterance.volume = 1.0;
            utterance.onend = () => setIsSpeaking(false);
            utterance.onerror = () => setIsSpeaking(false);
            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(utterance);
        } catch (error) {
            setIsSpeaking(false);
            console.error('Browser TTS error:', error);
        }
    };

    const speakText = async (text) => {
        try {
            setIsSpeaking(true);
            const response = await axios.post(`${API}/voice/speak?text=${encodeURIComponent(text.substring(0, 500))}`);
            
            if (response.data.audio) {
                playAudioResponse(response.data.audio);
            } else {
                speakWithBrowserVoice(text);
            }
        } catch (error) {
            console.error('TTS error:', error);
            speakWithBrowserVoice(text);
        }
    };

    const processWakePhrase = (spokenText) => {
        const normalized = (spokenText || '').toLowerCase().trim();
        const wakeMatch = normalized.match(/(?:^|\s)flora(?:\s|,|:|-)*(.*)/i);
        if (!wakeMatch) return;
        const now = Date.now();
        if (now - wakeCooldownRef.current < 2500) return;
        wakeCooldownRef.current = now;
        const command = (wakeMatch[1] || '').trim();
        setWakePhrase(spokenText);
        if (command) {
            clearWakePending();
            processVoiceTextCommand(command);
            return;
        }
        wakePendingRef.current = true;
        setWakeStatus('aguardando');
        scheduleWakePrompt();
    };

    const stopWakeListener = () => {
        if (recognitionRef.current) {
            recognitionRef.current.onend = null;
            recognitionRef.current.stop();
            recognitionRef.current = null;
        }
        setWakeStatus('inativo');
    };

    const clearWakePending = () => {
        wakePendingRef.current = false;
        if (wakeTimeoutRef.current) {
            clearTimeout(wakeTimeoutRef.current);
            wakeTimeoutRef.current = null;
        }
    };

    const stopManualVoiceCapture = () => {
        if (manualRecognitionRef.current) {
            manualRecognitionRef.current.onend = null;
            manualRecognitionRef.current.stop();
            manualRecognitionRef.current = null;
        }
        setManualListening(false);
    };

    const scheduleWakePrompt = () => {
        if (wakeTimeoutRef.current) {
            clearTimeout(wakeTimeoutRef.current);
        }
        wakeTimeoutRef.current = setTimeout(() => {
            if (wakePendingRef.current && voiceEnabled) {
                speakText('O que precisa candidato');
            }
        }, 5000);
    };

    const processVoiceTextCommand = async (text) => {
        const cleanText = (text || '').trim();
        if (!cleanText) return;

        setIsProcessingVoice(true);

        try {
            const response = await axios.post(`${API}/voice/text-command`, { text: cleanText });
            const { transcribed_text, response_text, audio_response, action, action_data, success } = response.data;

            setLastTranscription(transcribed_text);

            if (transcribed_text) {
                const userMessage = {
                    role: 'user',
                    content: `🎤 ${transcribed_text}`,
                    timestamp: new Date().toISOString(),
                    isVoice: true
                };
                setMessages(prev => [...prev, userMessage]);
            }

            if (response_text) {
                const assistantMessage = {
                    role: 'assistant',
                    content: response_text,
                    timestamp: new Date().toISOString(),
                    isVoice: true
                };
                setMessages(prev => [...prev, assistantMessage]);
            }

            if (audio_response && voiceEnabled) {
                playAudioResponse(audio_response);
            }

            if (action && action_data) {
                handleVoiceAction(action, action_data);
            }

            if (!success) {
                toast.error('Não consegui entender o comando');
            }
        } catch (error) {
            toast.error('Erro ao processar comando de voz');
            console.error('Voice text command error:', error);
        } finally {
            setIsProcessingVoice(false);
        }
    };

    const startManualVoiceCapture = async () => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            toast.error('Reconhecimento de voz indisponível neste navegador');
            return;
        }

        if (manualListening) {
            stopManualVoiceCapture();
            return;
        }

        const granted = wakePermission === 'granted' ? true : await requestMicrophoneAccess();
        if (!granted) {
            toast.error('Permita o acesso ao microfone para usar a escuta da Flora');
            return;
        }

        stopWakeListener();
        clearWakePending();

        const recognition = new SpeechRecognition();
        recognition.lang = 'pt-BR';
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
            setManualListening(true);
            setWakeStatus('escutando');
        };

        recognition.onresult = (event) => {
            const transcript = event?.results?.[0]?.[0]?.transcript?.trim();
            if (!transcript) {
                toast.error('Não consegui captar o comando de voz');
                return;
            }
            processVoiceTextCommand(transcript);
        };

        recognition.onerror = (event) => {
            const error = event?.error;
            if (error === 'not-allowed' || error === 'service-not-allowed') {
                setWakePermission('denied');
                toast.error('O navegador bloqueou o microfone');
            } else if (error === 'no-speech') {
                toast.error('Nenhuma fala detectada');
            } else {
                toast.error('Erro ao capturar áudio no navegador');
            }
            setWakeStatus('erro');
        };

        recognition.onend = () => {
            manualRecognitionRef.current = null;
            setManualListening(false);
            setWakeStatus('ouvindo');
            if (wakeEnabled && wakeSupported && wakePermission !== 'denied' && !isProcessingVoice) {
                setTimeout(() => startWakeListener(), 300);
            }
        };

        manualRecognitionRef.current = recognition;
        recognition.start();
    };

    const requestMicrophoneAccess = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach(track => track.stop());
            setWakePermission('granted');
            return true;
        } catch (error) {
            console.error('Microphone permission error:', error);
            setWakePermission('denied');
            return false;
        }
    };

    const startWakeListener = () => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) return;
        if (recognitionRef.current) return;

        const recognition = new SpeechRecognition();
        recognition.lang = 'pt-BR';
        recognition.continuous = true;
        recognition.interimResults = false;

        recognition.onstart = () => setWakeStatus('ouvindo');
        recognition.onresult = (event) => {
            for (let i = event.resultIndex; i < event.results.length; i += 1) {
                const result = event.results[i];
                if (!result || !result[0]) continue;
                const transcript = (result[0].transcript || '').trim();
                if (transcript) {
                    if (wakePendingRef.current) {
                        clearWakePending();
                        if (/flora/i.test(transcript)) {
                            processWakePhrase(transcript);
                        } else {
                            processVoiceTextCommand(transcript);
                        }
                    } else {
                        processWakePhrase(transcript);
                    }
                }
            }
        };
        recognition.onerror = (event) => {
            if (event?.error === 'not-allowed' || event?.error === 'service-not-allowed') {
                setWakeStatus('permissao-negada');
                setWakePermission('denied');
                return;
            }
            setWakeStatus('erro');
        };
        recognition.onend = () => {
            recognitionRef.current = null;
            if (wakeEnabled && wakePermission !== 'denied' && !isProcessingVoice) {
                setTimeout(() => startWakeListener(), 500);
            } else {
                setWakeStatus('inativo');
            }
        };

        recognitionRef.current = recognition;
        recognition.start();
    };

    useEffect(() => {
        if (wakeEnabled && wakeSupported && wakePermission !== 'denied' && !isProcessingVoice && !manualListening) {
            startWakeListener();
        } else {
            stopWakeListener();
            if (!manualListening) {
                setWakeStatus('inativo');
            }
        }

        return () => {
            stopWakeListener();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [wakeEnabled, wakeSupported, wakePermission, isProcessingVoice, manualListening]);

    useEffect(() => () => {
        stopWakeListener();
        stopManualVoiceCapture();
    }, []);

    const formatMessage = (content) => {
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br/>')
            .replace(/- /g, '• ');
    };

    return (
        <Layout>
            <div className="min-h-[calc(100vh-120px)]">
                <section className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
                    <div className="space-y-5">
                        <Card className="overflow-hidden rounded-[2rem] border-white/70 bg-[radial-gradient(circle_at_top,#fff7f7_0%,#ffffff_72%)] shadow-[0_18px_50px_rgba(15,23,42,0.06)]">
                            <CardHeader className="pb-4">
                                <div className="inline-flex w-fit items-center gap-2 rounded-full border border-primary/15 bg-white/80 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-primary">
                                    Flora
                                </div>
                                <CardTitle className="text-3xl font-black tracking-[-0.05em] text-slate-950">
                                    Um chat para tocar a rotina eleitoral sem sair do fluxo.
                                </CardTitle>
                                <CardDescription className="max-w-sm text-sm leading-6 text-slate-600">
                                    Menos cara de dashboard, mais conversa direta. Texto e voz continuam no mesmo fluxo operacional.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-3">
                                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                                    <div className="rounded-[1.5rem] border border-primary/10 bg-white/85 p-4">
                                        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-primary">Despesas</p>
                                        <p className="mt-3 text-3xl font-black tracking-[-0.04em] text-slate-950">
                                            {proactiveSummary?.pendingExpensesCount ?? 0}
                                        </p>
                                        <p className="mt-1 text-sm text-slate-600">
                                            pendentes, somando {formatCurrency(proactiveSummary?.pendingExpensesValue || 0)}
                                        </p>
                                    </div>
                                    <div className="rounded-[1.5rem] border border-emerald-100 bg-emerald-50/80 p-4">
                                        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-emerald-700">Vencimentos</p>
                                        <p className="mt-3 text-3xl font-black tracking-[-0.04em] text-slate-950">
                                            {proactiveSummary?.dueSoonCount ?? 0}
                                        </p>
                                        <p className="mt-1 text-sm text-slate-600">alertas ativos nos próximos 7 dias</p>
                                    </div>
                                </div>
                                <div className="flex flex-wrap gap-2 pt-1">
                                    <Button
                                        variant={voiceEnabled ? 'default' : 'outline'}
                                        onClick={() => setVoiceEnabled(!voiceEnabled)}
                                        className="gap-2 rounded-full px-4"
                                    >
                                        {voiceEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
                                        {voiceEnabled ? 'Voz ativa' : 'Ativar voz'}
                                    </Button>
                                    <Button
                                        variant="outline"
                                        onClick={clearHistory}
                                        className="gap-2 rounded-full px-4 text-destructive hover:text-destructive"
                                    >
                                        <Trash2 className="h-4 w-4" />
                                        Limpar
                                    </Button>
                                </div>
                                {alerts.length > 0 && (
                                    <div className="flex flex-wrap gap-2 pt-2">
                                        {alerts.map((alert, i) => (
                                            <Badge
                                                key={i}
                                                variant="outline"
                                                className="rounded-full border-amber-200 bg-amber-50 px-3 py-1 text-amber-700"
                                            >
                                                {alert}
                                            </Badge>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        <Card className="rounded-[1.75rem] border-white/70 bg-white/85 shadow-[0_18px_50px_rgba(15,23,42,0.06)]">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500">
                                    Escuta ativa
                                </CardTitle>
                                <CardDescription>
                                    Estado do microfone e do gatilho por voz.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                                                Status
                                            </p>
                                            <p className="mt-1 text-lg font-bold text-slate-950">{wakeStatus}</p>
                                        </div>
                                        <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${
                                            wakeStatus === 'ouvindo' || manualListening
                                                ? 'bg-emerald-100 text-emerald-700'
                                                : wakePermission === 'denied'
                                                    ? 'bg-amber-100 text-amber-600'
                                                    : 'bg-slate-100 text-slate-500'
                                        }`}>
                                            <Mic className="h-5 w-5" />
                                        </div>
                                    </div>
                                    <p className="mt-3 text-sm text-slate-600">
                                        {!wakeSupported
                                            ? 'Reconhecimento de voz indisponível neste navegador.'
                                            : wakePermission === 'denied'
                                                ? 'Microfone bloqueado nas permissões do navegador.'
                                                : manualListening
                                                    ? 'Escuta manual ativa. Fale agora e a Flora envia o comando.'
                                                    : 'Diga "Flora" ou toque no microfone para falar com a assistente.'}
                                    </p>
                                </div>

                                {wakePhrase && (
                                    <div className="rounded-2xl bg-[#fff7f7] p-4 text-sm text-slate-700">
                                        <span className="font-semibold text-slate-950">Frase detectada:</span> "{wakePhrase}"
                                    </div>
                                )}

                                {lastTranscription && (
                                    <div className="rounded-2xl bg-slate-50 p-4 text-sm text-slate-700">
                                        <span className="font-semibold text-slate-950">Último comando:</span> "{lastTranscription}"
                                    </div>
                                )}

                                {isSpeaking && (
                                    <div className="flex items-center justify-between rounded-2xl border border-primary/10 bg-primary/5 px-4 py-3">
                                        <div className="flex items-center gap-2 text-primary">
                                            <Radio className="h-4 w-4 animate-pulse" />
                                            <span className="text-sm font-medium">Flora está falando</span>
                                        </div>
                                        <Button variant="ghost" size="sm" onClick={stopSpeaking}>
                                            <VolumeX className="h-4 w-4" />
                                        </Button>
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        <Card className="rounded-[1.75rem] border-white/70 bg-white/85 shadow-[0_18px_50px_rgba(15,23,42,0.06)]">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500">
                                    Ações rápidas
                                </CardTitle>
                                <CardDescription>
                                    Prompts para abrir a conversa.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-2">
                                {quickActions.map((action, i) => (
                                    <button
                                        key={i}
                                        type="button"
                                        onClick={() => sendMessage(action.prompt)}
                                        disabled={loading}
                                        data-testid={`quick-action-${i}`}
                                        className="flex w-full items-center gap-3 rounded-2xl border border-transparent bg-slate-50 px-4 py-3 text-left transition hover:border-primary/20 hover:bg-[#fff7f7]"
                                    >
                                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white text-primary shadow-sm">
                                            <action.icon className="h-4 w-4" />
                                        </div>
                                        <div>
                                            <p className="text-sm font-semibold text-slate-950">{action.label}</p>
                                            <p className="text-xs text-slate-500">{action.prompt}</p>
                                        </div>
                                    </button>
                                ))}
                            </CardContent>
                        </Card>

                        <Card className="rounded-[1.75rem] border-white/70 bg-white/85 shadow-[0_18px_50px_rgba(15,23,42,0.06)]">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-500">
                                    Exemplos de comando
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2">
                                {voiceExamples.map((example, i) => (
                                    <div key={i} className="rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
                                        "{example}"
                                    </div>
                                ))}
                            </CardContent>
                        </Card>
                    </div>

                    <Card className="flex min-h-[780px] flex-col overflow-hidden rounded-[2.2rem] border-white/80 bg-[linear-gradient(180deg,#fffaf9_0%,#ffffff_16%,#fff7f2_100%)] shadow-[0_24px_80px_rgba(15,23,42,0.08)]">
                        <CardHeader className="border-b border-slate-100/80 bg-white/70 backdrop-blur">
                            <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
                                <div className="flex min-w-0 flex-1 items-center gap-3">
                                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-950 text-white shadow-[0_16px_32px_rgba(15,23,42,0.18)]">
                                        <Bot className="h-5 w-5" />
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <CardTitle className="text-xl font-bold text-slate-950">Flora</CardTitle>
                                            <Badge className="rounded-full border-0 bg-primary/10 px-3 py-1 text-primary">
                                                {wakeSupported ? (manualListening ? 'voz manual' : `voz ${wakeStatus}`) : 'texto'}
                                            </Badge>
                                        </div>
                                        <CardDescription>
                                            Assistente operacional da Ativa Eleitoral
                                        </CardDescription>
                                    </div>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <Button
                                        variant="outline"
                                        onClick={() => sendMessage('Flora, me lembre os próximos pagamentos e contratos pendentes')}
                                        className="rounded-full px-4"
                                    >
                                        <Sparkles className="mr-2 h-4 w-4" />
                                        Revisar pendências
                                    </Button>
                                    <div className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600">
                                        {sessionId ? `Sessão ${String(sessionId).slice(0, 8)}` : 'Nova conversa'}
                                    </div>
                                </div>
                            </div>
                            <div className="mt-4 flex flex-wrap gap-2">
                                {quickActions.map((action) => (
                                    <button
                                        key={action.label}
                                        type="button"
                                        onClick={() => sendMessage(action.prompt)}
                                        className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-primary/25 hover:text-primary"
                                    >
                                        {action.label}
                                    </button>
                                ))}
                            </div>
                        </CardHeader>

                        <ScrollArea className="flex-1 px-5 py-6 md:px-7" ref={scrollRef}>
                            {loadingHistory ? (
                                <div className="flex h-40 items-center justify-center">
                                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                </div>
                            ) : messages.length === 0 ? (
                                <div className="flex h-full min-h-[420px] flex-col items-center justify-center text-center">
                                    <div className="flex h-24 w-24 items-center justify-center rounded-[2rem] bg-slate-950 text-white shadow-[0_20px_40px_rgba(15,23,42,0.12)]">
                                        <Bot className="h-10 w-10" />
                                    </div>
                                    <h2 className="mt-6 font-heading text-3xl font-black tracking-[-0.04em] text-slate-950">
                                        Olá, {perfil}.
                                    </h2>
                                    <p className="mt-3 max-w-md text-sm leading-6 text-slate-600">
                                        Posso revisar despesas, abrir contratos, priorizar vencimentos e orientar sua prestação de contas.
                                    </p>
                                    <div className="mt-6 flex flex-wrap justify-center gap-2">
                                        {quickActions.slice(0, 3).map((action) => (
                                            <button
                                                key={action.label}
                                                type="button"
                                                onClick={() => sendMessage(action.prompt)}
                                                className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-primary/25 hover:text-primary"
                                            >
                                                {action.label}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                <div className="space-y-5">
                                    {messages.map((msg, i) => (
                                        <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                            <div className={`max-w-[88%] rounded-[1.8rem] px-5 py-4 shadow-sm ${
                                                msg.role === 'user'
                                                    ? 'bg-slate-950 text-white'
                                                    : 'border border-white/80 bg-white/90 text-slate-900'
                                            }`}>
                                                {msg.role === 'assistant' && (
                                                    <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                                                        <Bot className="h-3.5 w-3.5" />
                                                        Flora
                                                        {msg.isVoice && <Mic className="h-3.5 w-3.5 text-primary/70" />}
                                                    </div>
                                                )}
                                                <div
                                                    className="text-sm leading-7"
                                                    dangerouslySetInnerHTML={{ __html: formatMessage(msg.content) }}
                                                />
                                                <div className={`mt-3 text-[11px] ${msg.role === 'user' ? 'text-white/65' : 'text-slate-400'}`}>
                                                    {new Date(msg.timestamp).toLocaleTimeString('pt-BR', {
                                                        hour: '2-digit',
                                                        minute: '2-digit'
                                                    })}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                    {loading && (
                                        <div className="flex justify-start">
                                            <div className="rounded-[1.6rem] border border-white/70 bg-white px-5 py-4 shadow-sm">
                                                <div className="flex items-center gap-2">
                                                    <Loader2 className="h-4 w-4 animate-spin text-primary" />
                                                    <span className="text-sm text-slate-500">Flora está organizando a resposta...</span>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </ScrollArea>

                        <div className="border-t border-slate-100 bg-white p-4 md:p-5">
                            <div className="flex items-end gap-3">
                                <div className="flex-1 rounded-[1.9rem] border border-slate-200 bg-white px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
                                    <div className="flex items-center gap-3">
                                        <Input
                                            ref={inputRef}
                                            value={inputMessage}
                                            onChange={(e) => setInputMessage(e.target.value)}
                                            onKeyPress={handleKeyPress}
                                            placeholder="Pergunte sobre pagamentos, contratos, despesas ou conformidade"
                                            disabled={loading}
                                            className="h-auto border-0 bg-transparent px-0 py-0 text-sm focus-visible:ring-0 focus-visible:ring-offset-0"
                                            data-testid="chat-input"
                                        />
                                        {wakeSupported && (
                                            <div
                                                className={`flex h-10 w-10 items-center justify-center rounded-2xl border transition ${
                                                    wakeStatus === 'ouvindo' || manualListening
                                                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                                        : wakePermission === 'denied'
                                                            ? 'border-amber-200 bg-amber-50 text-amber-600'
                                                            : 'border-slate-200 bg-white text-slate-500'
                                                }`}
                                                title={manualListening ? 'Parar escuta manual' : 'Falar com a Flora'}
                                                onClick={startManualVoiceCapture}
                                                role="button"
                                                tabIndex={0}
                                                onKeyDown={(e) => {
                                                    if (e.key === 'Enter' || e.key === ' ') {
                                                        e.preventDefault();
                                                        startManualVoiceCapture();
                                                    }
                                                }}
                                            >
                                                <Mic className="h-4 w-4" />
                                            </div>
                                        )}
                                    </div>
                                </div>
                                <Button
                                    onClick={() => sendMessage()}
                                    disabled={loading || !inputMessage.trim()}
                                    className="h-12 w-12 rounded-2xl p-0 shadow-[0_16px_32px_rgba(239,68,68,0.24)]"
                                    data-testid="send-message-btn"
                                >
                                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                                </Button>
                            </div>
                            <p className="mt-3 text-xs text-slate-500">
                                Enter para enviar. Diga "Flora" ou toque no microfone para falar.
                            </p>
                        </div>
                    </Card>
                </section>
            </div>
        </Layout>
    );
}


