import { useState, useEffect, useRef } from 'react';
import { Layout } from '../components/Layout';
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
    FileText, BarChart3, Shield,
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
    const [autoWakeAvailable, setAutoWakeAvailable] = useState(true);
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
        const supported = Boolean(SpeechRecognition);
        setWakeSupported(supported);
        setAutoWakeAvailable(supported);
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
        setWakeStatus(autoWakeAvailable ? 'inativo' : 'manual');
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
            setWakeStatus(autoWakeAvailable ? 'ouvindo' : 'manual');
            if (wakeEnabled && wakeSupported && autoWakeAvailable && wakePermission !== 'denied' && !isProcessingVoice) {
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
            const error = event?.error;
            if (error === 'not-allowed' || error === 'service-not-allowed') {
                setWakeStatus('permissao-negada');
                setWakePermission('denied');
                return;
            }
            if (error === 'aborted' || error === 'no-speech') {
                setWakeStatus('ouvindo');
                return;
            }
            setAutoWakeAvailable(false);
            setWakeStatus('manual');
            toast.error('Escuta automática indisponível neste navegador. Use o microfone.');
        };
        recognition.onend = () => {
            recognitionRef.current = null;
            if (wakeEnabled && autoWakeAvailable && wakePermission !== 'denied' && !isProcessingVoice) {
                setTimeout(() => startWakeListener(), 500);
            } else {
                setWakeStatus(autoWakeAvailable ? 'inativo' : 'manual');
            }
        };

        recognitionRef.current = recognition;
        recognition.start();
    };

    useEffect(() => {
        if (wakeEnabled && wakeSupported && autoWakeAvailable && wakePermission !== 'denied' && !isProcessingVoice && !manualListening) {
            startWakeListener();
        } else {
            stopWakeListener();
            if (!manualListening) {
                setWakeStatus(autoWakeAvailable ? 'inativo' : 'manual');
            }
        }

        return () => {
            stopWakeListener();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [wakeEnabled, wakeSupported, autoWakeAvailable, wakePermission, isProcessingVoice, manualListening]);

    useEffect(() => () => {
        if (recognitionRef.current) {
            recognitionRef.current.onend = null;
            recognitionRef.current.stop();
            recognitionRef.current = null;
        }
        if (manualRecognitionRef.current) {
            manualRecognitionRef.current.onend = null;
            manualRecognitionRef.current.stop();
            manualRecognitionRef.current = null;
        }
    }, []);

    const formatMessage = (content) => {
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br/>')
            .replace(/- /g, '• ');
    };

    return (
        <Layout immersive hideFloatingAssistant>
            <div className="relative min-h-screen overflow-hidden bg-[#120507] text-white">
                <div className="pointer-events-none absolute inset-0 opacity-80">
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(143,13,24,0.42)_0%,rgba(18,5,7,0)_38%)]" />
                    <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,70,70,0.12)_0%,transparent_18%),radial-gradient(circle_at_80%_15%,rgba(255,110,110,0.08)_0%,transparent_16%),radial-gradient(circle_at_30%_75%,rgba(255,255,255,0.05)_0%,transparent_14%)]" />
                    <div className="absolute inset-0 bg-[radial-gradient(rgba(255,255,255,0.1)_1px,transparent_1px)] [background-size:140px_140px]" />
                    <div className="absolute inset-y-0 left-[7%] w-px bg-white/6" />
                    <div className="absolute inset-y-0 right-[7%] w-px bg-white/6" />
                </div>

                <div className="relative mx-auto flex h-screen max-w-[1640px] flex-col px-5 pb-6 pt-8 md:px-8">
                    <div className="mx-auto flex w-full max-w-[1320px] flex-col gap-4">
                        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                            <div className="min-w-0">
                                <p className="text-[11px] uppercase tracking-[0.38em] text-white/40">
                                    Flora
                                </p>
                                <h1 className="mt-3 text-3xl font-black tracking-[-0.05em] text-white md:text-4xl">
                                    Olá, {perfil}.
                                </h1>
                                <p className="mt-2 max-w-2xl text-sm leading-6 text-white/62 md:text-base">
                                    Use a Flora para organizar a operação eleitoral, registrar movimentações e entender o que precisa da sua atenção.
                                </p>
                            </div>

                            <div className="flex flex-wrap items-center gap-2">
                                <Badge className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-white/78">
                                    {manualListening
                                        ? 'escuta manual'
                                        : autoWakeAvailable && wakeSupported
                                            ? `auto ${wakeStatus}`
                                            : wakePermission === 'denied'
                                                ? 'microfone bloqueado'
                                                : 'modo manual'}
                                </Badge>
                                <Badge className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-white/60">
                                    {proactiveSummary?.pendingExpensesCount ?? 0} despesas
                                </Badge>
                                <Badge className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-white/60">
                                    {proactiveSummary?.dueSoonCount ?? 0} vencimentos
                                </Badge>
                                <Button
                                    variant="ghost"
                                    onClick={() => setVoiceEnabled(!voiceEnabled)}
                                    className="rounded-full border border-white/12 bg-white/5 px-4 text-white hover:bg-white/10 hover:text-white"
                                >
                                    {voiceEnabled ? <Volume2 className="mr-2 h-4 w-4" /> : <VolumeX className="mr-2 h-4 w-4" />}
                                    {voiceEnabled ? 'voz ativa' : 'voz desligada'}
                                </Button>
                                <Button
                                    variant="ghost"
                                    onClick={clearHistory}
                                    className="rounded-full border border-white/12 bg-white/5 px-4 text-white/70 hover:bg-white/10 hover:text-white"
                                >
                                    <Trash2 className="mr-2 h-4 w-4" />
                                    nova conversa
                                </Button>
                            </div>
                        </div>

                        <div className="flex flex-wrap gap-2">
                            {quickActions.map((action) => (
                                <button
                                    key={action.label}
                                    type="button"
                                    onClick={() => sendMessage(action.prompt)}
                                    className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm font-medium text-white/70 transition hover:border-white/20 hover:bg-white/[0.06] hover:text-white"
                                >
                                    {action.label}
                                </button>
                            ))}
                        </div>

                        {(alerts.length > 0 || lastTranscription || wakePhrase || isSpeaking) && (
                            <div className="flex flex-wrap gap-2">
                                {alerts.map((alert, i) => (
                                    <Badge
                                        key={i}
                                        className="rounded-full border border-[#a73d3d]/40 bg-[#381114] px-3 py-1 text-[#ffb4b4]"
                                    >
                                        {alert}
                                    </Badge>
                                ))}
                                {wakePhrase && (
                                    <Badge className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-white/60">
                                        gatilho: {wakePhrase}
                                    </Badge>
                                )}
                                {lastTranscription && (
                                    <Badge className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-white/60">
                                        último comando: {lastTranscription}
                                    </Badge>
                                )}
                                {isSpeaking && (
                                    <Badge className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-white/60">
                                        Flora está falando
                                    </Badge>
                                )}
                            </div>
                        )}
                    </div>

                    <ScrollArea className="flora-scroll mt-6 flex-1 px-1" ref={scrollRef}>
                        <div className="mx-auto flex min-h-full w-full max-w-[1320px] flex-col">
                        {loadingHistory ? (
                            <div className="flex h-40 items-center justify-center">
                                <Loader2 className="h-6 w-6 animate-spin text-white/50" />
                            </div>
                        ) : messages.length === 0 ? (
                            <div className="flex flex-1 flex-col items-center justify-center pb-28 pt-12 text-center">
                                <div className="flex h-24 w-24 items-center justify-center rounded-[2rem] border border-white/10 bg-black/30 text-white shadow-[0_24px_60px_rgba(0,0,0,0.28)]">
                                    <Bot className="h-10 w-10" />
                                </div>
                                <h2 className="mt-8 text-4xl font-black tracking-[-0.05em] text-white md:text-5xl">
                                    Olá, {perfil}.
                                </h2>
                                <p className="mt-4 max-w-xl text-base leading-7 text-white/62">
                                    Posso revisar despesas, abrir contratos, priorizar vencimentos e orientar sua prestação de contas em uma conversa contínua.
                                </p>
                                <div className="mt-8 flex flex-wrap justify-center gap-2">
                                    {quickActions.map((action) => (
                                        <button
                                            key={action.label}
                                            type="button"
                                            onClick={() => sendMessage(action.prompt)}
                                            className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-sm font-medium text-white/70 transition hover:border-white/20 hover:bg-white/[0.06] hover:text-white"
                                        >
                                            {action.label}
                                        </button>
                                    ))}
                                </div>
                                <p className="mt-6 text-sm text-white/45">
                                    {autoWakeAvailable && wakeSupported
                                        ? 'Diga "Flora" para escuta automática ou use o microfone.'
                                        : 'Use o microfone para falar com a Flora neste navegador.'}
                                </p>
                            </div>
                        ) : (
                            <div className="mx-auto flex w-full max-w-[1080px] flex-col gap-10 pb-28 pt-8">
                                {messages.map((msg, i) => (
                                    <div
                                        key={i}
                                        className={`flex animate-fade-in-up ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                                    >
                                        <div className={`max-w-[88%] md:max-w-[62%] ${
                                            msg.role === 'user'
                                                ? 'rounded-[1.75rem] border border-[#632024] bg-[linear-gradient(180deg,rgba(93,23,30,0.94)_0%,rgba(67,15,20,0.96)_100%)] px-5 py-4 text-white shadow-[0_18px_50px_rgba(0,0,0,0.24)]'
                                                : 'flex items-start gap-4 text-white'
                                        }`}>
                                            {msg.role === 'assistant' && (
                                                <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#7d242c] bg-[#1c090b] text-[#ff4d57]">
                                                    <Bot className="h-3.5 w-3.5" />
                                                </div>
                                            )}
                                            <div className={msg.role === 'assistant' ? 'rounded-[1.75rem] bg-white/[0.04] px-5 py-4 shadow-[0_18px_50px_rgba(0,0,0,0.16)] backdrop-blur-sm' : ''}>
                                                {msg.role === 'assistant' && (
                                                    <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-white/42">
                                                        Flora
                                                        {msg.isVoice && <Mic className="h-3.5 w-3.5 text-white/28" />}
                                                    </div>
                                                )}
                                                <div
                                                    className={`text-sm leading-7 md:text-[15px] ${msg.role === 'assistant' ? 'text-white/92' : 'text-white'}`}
                                                    dangerouslySetInnerHTML={{ __html: formatMessage(msg.content) }}
                                                />
                                                <div className={`mt-3 text-[11px] ${msg.role === 'user' ? 'text-white/55' : 'text-white/34'}`}>
                                                    {new Date(msg.timestamp).toLocaleTimeString('pt-BR', {
                                                        hour: '2-digit',
                                                        minute: '2-digit'
                                                    })}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                                {loading && (
                                    <div className="flex justify-start">
                                        <div className="flex items-start gap-4">
                                            <div className="mt-1 flex h-8 w-8 items-center justify-center rounded-full border border-[#7d242c] bg-[#1c090b] text-[#ff4d57]">
                                                <Bot className="h-3.5 w-3.5" />
                                            </div>
                                            <div className="rounded-[1.75rem] bg-white/[0.04] px-5 py-4 shadow-[0_18px_50px_rgba(0,0,0,0.16)] backdrop-blur-sm">
                                                <div className="flex items-center gap-2">
                                                    <Loader2 className="h-4 w-4 animate-spin text-[#ff5a63]" />
                                                    <span className="text-sm text-white/56">Flora está organizando a resposta...</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                        </div>
                    </ScrollArea>

                    <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-[linear-gradient(180deg,rgba(18,5,7,0)_0%,rgba(18,5,7,0.94)_34%,#120507_100%)] px-5 pb-6 pt-16 md:px-8">
                        <div className="pointer-events-auto mx-auto w-full max-w-[1080px]">
                            <div className="flex items-end gap-3 rounded-[2rem] border border-white/16 bg-black/26 px-4 py-4 shadow-[0_24px_80px_rgba(0,0,0,0.35)] backdrop-blur-xl">
                                <div className="flex-1">
                                    <p className="mb-2 text-[11px] uppercase tracking-[0.22em] text-white/28">
                                        Mensagem
                                    </p>
                                    <Input
                                        ref={inputRef}
                                        value={inputMessage}
                                        onChange={(e) => setInputMessage(e.target.value)}
                                        onKeyPress={handleKeyPress}
                                        placeholder="Digite sua mensagem..."
                                        disabled={loading}
                                        className="h-auto border-0 bg-transparent px-0 py-0 text-base text-white placeholder:text-white/26 focus-visible:ring-0 focus-visible:ring-offset-0"
                                        data-testid="chat-input"
                                    />
                                </div>

                                <div className="flex items-center gap-3">
                                    {wakeSupported && (
                                        <button
                                            type="button"
                                            className={`flex h-11 w-11 items-center justify-center rounded-full border transition ${
                                                manualListening
                                                    ? 'border-emerald-300/40 bg-emerald-400/12 text-emerald-200'
                                                    : wakePermission === 'denied'
                                                        ? 'border-amber-300/40 bg-amber-400/12 text-amber-200'
                                                        : 'border-white/12 bg-white/[0.04] text-white/55 hover:border-white/22 hover:bg-white/[0.08] hover:text-white'
                                            }`}
                                            title={manualListening ? 'Parar escuta manual' : 'Falar com a Flora'}
                                            onClick={startManualVoiceCapture}
                                            data-testid="manual-voice-btn"
                                        >
                                            <Mic className="h-4 w-4" />
                                        </button>
                                    )}
                                    <Button
                                        onClick={() => sendMessage()}
                                        disabled={loading || !inputMessage.trim()}
                                        className="h-11 w-11 rounded-full bg-[#ff3b3f] p-0 text-white shadow-[0_18px_40px_rgba(255,59,63,0.36)] hover:bg-[#ff4a4e]"
                                        data-testid="send-message-btn"
                                    >
                                        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                                    </Button>
                                </div>
                            </div>
                        <div className="mx-auto mt-3 flex w-full max-w-[1080px] items-center justify-between gap-3 text-xs text-white/34">
                            <span>
                                {autoWakeAvailable && wakeSupported
                                    ? 'Escuta automática ativa quando o navegador permitir. Você também pode usar o microfone.'
                                    : 'Escuta automática indisponível neste navegador. Use o microfone para falar com a Flora.'}
                            </span>
                            {isSpeaking && (
                                <button
                                    type="button"
                                    onClick={stopSpeaking}
                                    className="inline-flex items-center gap-2 rounded-full border border-white/12 px-3 py-1 text-white/52 transition hover:bg-white/[0.04] hover:text-white"
                                >
                                    <Radio className="h-3.5 w-3.5 animate-pulse" />
                                    parar áudio
                                </button>
                            )}
                        </div>
                    </div>
                    </div>
                </div>
            </div>
        </Layout>
    );
}


