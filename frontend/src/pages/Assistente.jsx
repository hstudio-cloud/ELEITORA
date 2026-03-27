import { useState, useEffect, useRef } from 'react';
import { Layout } from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import axios from 'axios';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { 
    Bot, Send, Loader2, Trash2, AlertTriangle, 
    FileText, BarChart3, Shield, Sparkles, MessageSquare,
    ChevronRight, RefreshCw, Mic, MicOff, Volume2, VolumeX,
    Radio, Waves, StopCircle
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
    "Flora, qual é meu saldo?",
    "Flora, tenho alguma despesa pra gerar?",
    "Flora, tem contrato pra fazer?",
    "Flora, quais pagamentos vencem esta semana?",
    "Adicionar despesa de 500 reais em publicidade",
    "Mostrar contratos pendentes"
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
    const [isRecording, setIsRecording] = useState(false);
    const [isProcessingVoice, setIsProcessingVoice] = useState(false);
    const [isSpeaking, setIsSpeaking] = useState(false);
    const [voiceEnabled, setVoiceEnabled] = useState(true);
    const [wakeEnabled, setWakeEnabled] = useState(true);
    const [wakeSupported, setWakeSupported] = useState(false);
    const [wakeStatus, setWakeStatus] = useState('inativo');
    const [wakePhrase, setWakePhrase] = useState('');
    const [lastTranscription, setLastTranscription] = useState('');
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const audioRef = useRef(null);
    const recognitionRef = useRef(null);
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
                    greeting += `Tenho um resumo rápido:\n`;
                    if (summary.pendingExpensesCount > 0) {
                        greeting += `💰 ${summary.pendingExpensesCount} despesa(s) pendente(s) (R$ ${summary.pendingExpensesValue.toFixed(2)})\n`;
                    }
                    if (summary.dueSoonCount > 0) {
                        greeting += `⏰ ${summary.dueSoonCount} pagamento(s) vencendo em 7 dias\n`;
                    }
                    if (summary.unsignedContractsCount > 0) {
                        greeting += `📋 ${summary.unsignedContractsCount} contrato(s) para finalizar\n`;
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
    
    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            mediaRecorderRef.current = mediaRecorder;
            audioChunksRef.current = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                stream.getTracks().forEach(track => track.stop());
                await processVoiceCommand(audioBlob);
            };

            mediaRecorder.start();
            setIsRecording(true);
            toast.info('🎤 Gravando... Fale seu comando');
        } catch (error) {
            toast.error('Erro ao acessar microfone. Verifique as permissões.');
            console.error('Microphone error:', error);
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        }
    };

    const processVoiceCommand = async (audioBlob) => {
        setIsProcessingVoice(true);
        
        try {
            const formData = new FormData();
            formData.append('audio', audioBlob, 'command.webm');

            const response = await axios.post(`${API}/voice/command`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            const { transcribed_text, response_text, audio_response, action, action_data, success } = response.data;

            setLastTranscription(transcribed_text);

            // Add to chat history
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

            // Play audio response
            if (audio_response && voiceEnabled) {
                playAudioResponse(audio_response);
            }

            // Execute action if any
            if (action && action_data) {
                handleVoiceAction(action, action_data);
            }

            if (!success) {
                toast.error('Não consegui entender o comando');
            }
        } catch (error) {
            toast.error('Erro ao processar comando de voz');
            console.error('Voice command error:', error);
        } finally {
            setIsProcessingVoice(false);
        }
    };

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

    const requestMicrophoneAccess = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach(track => track.stop());
            return true;
        } catch (error) {
            console.error('Microphone permission error:', error);
            toast.error('Permita acesso ao microfone para ativar a Flora por nome.');
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
                setWakeEnabled(false);
                toast.error('Ative o microfone para usar a palavra-chave "Flora".');
                return;
            }
            setWakeStatus('erro');
        };
        recognition.onend = () => {
            recognitionRef.current = null;
            if (wakeEnabled && !isRecording && !isProcessingVoice) {
                setTimeout(() => startWakeListener(), 500);
            } else {
                setWakeStatus('inativo');
            }
        };

        recognitionRef.current = recognition;
        recognition.start();
    };

    useEffect(() => {
        if (wakeEnabled && wakeSupported && !isRecording && !isProcessingVoice) {
            startWakeListener();
        } else {
            stopWakeListener();
        }

        return () => {
            stopWakeListener();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [wakeEnabled, wakeSupported, isRecording, isProcessingVoice]);

    const formatMessage = (content) => {
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br/>')
            .replace(/- /g, '• ');
    };

    return (
        <Layout>
            <div className="space-y-6 h-[calc(100vh-120px)] flex flex-col">
                {/* Header */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div>
                        <h1 className="text-3xl font-heading font-bold flex items-center gap-3">
                            <div className="p-2 bg-gradient-to-br from-accent to-secondary rounded-lg">
                                <Bot className="h-6 w-6 text-white" />
                            </div>
                            Flora
                            <Badge variant="outline" className="ml-2 text-accent border-accent/50">
                                Assistente IA com Voz
                            </Badge>
                        </h1>
                        <p className="text-muted-foreground mt-1">
                            Converse por texto ou use comandos de voz. Diga "Flora" para ativar.
                        </p>
                    </div>
                    <div className="flex gap-2">
                        <Button 
                            variant={voiceEnabled ? "default" : "outline"}
                            size="sm" 
                            onClick={() => setVoiceEnabled(!voiceEnabled)}
                            className="gap-2"
                        >
                            {voiceEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
                            {voiceEnabled ? 'Voz Ativa' : 'Voz Desativada'}
                        </Button>
                        <Button
                            variant={wakeEnabled ? "default" : "outline"}
                            size="sm"
                            onClick={async () => {
                                if (!wakeEnabled) {
                                    const granted = await requestMicrophoneAccess();
                                    if (!granted) return;
                                }
                                setWakeEnabled(!wakeEnabled);
                            }}
                            className="gap-2"
                            disabled={!wakeSupported}
                        >
                            <Radio className="h-4 w-4" />
                            {wakeEnabled ? 'Flora Sempre Ouvindo' : 'Ativação por Nome'}
                        </Button>
                        <Button 
                            variant="outline" 
                            size="sm" 
                            onClick={clearHistory}
                            className="gap-2 text-destructive hover:text-destructive"
                        >
                            <Trash2 className="h-4 w-4" />
                            Limpar
                        </Button>
                    </div>
                </div>

                {/* Alerts */}
                {alerts.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                        {alerts.map((alert, i) => (
                            <Badge 
                                key={i} 
                                variant="outline" 
                                className="text-amber-400 border-amber-500/30 bg-amber-500/10"
                            >
                                {alert}
                            </Badge>
                        ))}
                    </div>
                )}

                {proactiveSummary && (
                    <Card className="border-accent/40 bg-accent/5">
                        <CardContent className="p-4">
                            <div className="flex flex-wrap items-center gap-3 text-sm">
                                <Badge variant="outline" className="border-accent/40 text-accent">Flora Ativa</Badge>
                                <span>{proactiveSummary.pendingExpensesCount} despesas pendentes</span>
                                <span>{proactiveSummary.dueSoonCount} vencimentos em 7 dias</span>
                                <span>{proactiveSummary.unsignedContractsCount} contratos para finalizar</span>
                                <Button
                                    size="sm"
                                    variant="secondary"
                                    className="ml-auto"
                                    onClick={() => sendMessage('Flora, me lembre os próximos pagamentos e contratos pendentes')}
                                >
                                    Revisar Pendências
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {/* Main Content */}
                <div className="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-4 min-h-0">
                    {/* Sidebar */}
                    <div className="lg:col-span-1 space-y-4">
                        {/* Voice Control Card */}
                        <Card className="border-accent/30 bg-accent/5">
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm font-medium flex items-center gap-2">
                                    <Mic className="h-4 w-4 text-accent" />
                                    Comando de Voz
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <Button
                                    className={`w-full h-20 text-lg gap-3 ${
                                        isRecording 
                                            ? 'bg-red-500 hover:bg-red-600 animate-pulse' 
                                            : isProcessingVoice 
                                                ? 'bg-amber-500'
                                                : 'bg-accent hover:bg-accent/90'
                                    }`}
                                    onClick={isRecording ? stopRecording : startRecording}
                                    disabled={isProcessingVoice}
                                    data-testid="voice-record-btn"
                                >
                                    {isRecording ? (
                                        <>
                                            <StopCircle className="h-6 w-6" />
                                            Parar
                                        </>
                                    ) : isProcessingVoice ? (
                                        <>
                                            <Loader2 className="h-6 w-6 animate-spin" />
                                            Processando...
                                        </>
                                    ) : (
                                        <>
                                            <Mic className="h-6 w-6" />
                                            Falar
                                        </>
                                    )}
                                </Button>
                                
                                {isRecording && (
                                    <div className="flex items-center justify-center gap-2 text-red-400">
                                        <Waves className="h-4 w-4 animate-pulse" />
                                        <span className="text-sm">Ouvindo...</span>
                                    </div>
                                )}

                                <div className="text-xs p-2 rounded bg-muted/40">
                                    <span className="font-medium">Ativação por nome:</span>{' '}
                                    {!wakeSupported
                                        ? 'Não suportado no navegador'
                                        : wakeEnabled
                                            ? `Ligado (${wakeStatus})`
                                            : 'Desligado'}
                                </div>

                                {wakePhrase && (
                                    <div className="text-xs text-muted-foreground p-2 bg-muted/50 rounded">
                                        <span className="font-medium">Frase detectada:</span>
                                        <br />&quot;{wakePhrase}&quot;
                                    </div>
                                )}
                                
                                {isSpeaking && (
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-2 text-accent">
                                            <Radio className="h-4 w-4 animate-pulse" />
                                            <span className="text-sm">Flora falando...</span>
                                        </div>
                                        <Button 
                                            variant="ghost" 
                                            size="sm"
                                            onClick={stopSpeaking}
                                        >
                                            <VolumeX className="h-4 w-4" />
                                        </Button>
                                    </div>
                                )}

                                {lastTranscription && (
                                    <div className="text-xs text-muted-foreground p-2 bg-muted/50 rounded">
                                        <span className="font-medium">Último comando:</span>
                                        <br />&quot;{lastTranscription}&quot;
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Quick Actions */}
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm font-medium flex items-center gap-2">
                                    <Sparkles className="h-4 w-4 text-accent" />
                                    Ações Rápidas
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-2">
                                {quickActions.map((action, i) => (
                                    <Button
                                        key={i}
                                        variant="ghost"
                                        className="w-full justify-start gap-2 h-auto py-3 text-left"
                                        onClick={() => sendMessage(action.prompt)}
                                        disabled={loading}
                                        data-testid={`quick-action-${i}`}
                                    >
                                        <action.icon className="h-4 w-4 text-muted-foreground shrink-0" />
                                        <span className="text-sm">{action.label}</span>
                                    </Button>
                                ))}
                            </CardContent>
                        </Card>

                        {/* Voice Examples */}
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-sm font-medium flex items-center gap-2">
                                    <MessageSquare className="h-4 w-4 text-muted-foreground" />
                                    Exemplos de Comandos
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <ul className="text-xs text-muted-foreground space-y-2">
                                    {voiceExamples.map((example, i) => (
                                        <li key={i} className="flex items-start gap-2">
                                            <span className="text-accent">•</span>
                                            &quot;{example}&quot;
                                        </li>
                                    ))}
                                </ul>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Chat Window */}
                    <Card className="lg:col-span-3 flex flex-col min-h-0">
                        <CardHeader className="pb-3 border-b">
                            <div className="flex items-center gap-2">
                                <MessageSquare className="h-5 w-5 text-accent" />
                                <CardTitle className="text-base">Conversa com Flora</CardTitle>
                            </div>
                        </CardHeader>
                        
                        {/* Messages */}
                        <ScrollArea className="flex-1 p-4" ref={scrollRef}>
                            {loadingHistory ? (
                                <div className="flex items-center justify-center h-40">
                                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                </div>
                            ) : messages.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-40 text-center">
                                    <div className="relative">
                                        <Bot className="h-16 w-16 text-accent/50 mb-4" />
                                        <Mic className="h-6 w-6 text-accent absolute -right-2 -bottom-2" />
                                    </div>
                                    <p className="text-lg font-medium text-foreground">
                                        Ola {perfil}, em que posso te ajudar hoje?
                                    </p>
                                    <p className="text-sm text-muted-foreground mt-1">
                                        Sua assistente de campanha com voz
                                    </p>
                                    <p className="text-xs text-muted-foreground/70 mt-2">
                                        Clique em &quot;Falar&quot;, diga &quot;Flora&quot; ou digite sua pergunta
                                    </p>
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {messages.map((msg, i) => (
                                        <div 
                                            key={i}
                                            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                                        >
                                            <div 
                                                className={`max-w-[85%] rounded-lg p-3 ${
                                                    msg.role === 'user' 
                                                        ? 'bg-accent text-accent-foreground' 
                                                        : 'bg-muted'
                                                }`}
                                            >
                                                {msg.role === 'assistant' && (
                                                    <div className="flex items-center gap-2 mb-2 pb-2 border-b border-border/50">
                                                        <Bot className="h-4 w-4 text-accent" />
                                                        <span className="text-xs font-medium text-accent">Flora</span>
                                                        {msg.isVoice && <Mic className="h-3 w-3 text-accent/70" />}
                                                    </div>
                                                )}
                                                <div 
                                                    className="text-sm leading-relaxed"
                                                    dangerouslySetInnerHTML={{ __html: formatMessage(msg.content) }}
                                                />
                                                <div className="text-xs text-muted-foreground/70 mt-2">
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
                                            <div className="bg-muted rounded-lg p-3">
                                                <div className="flex items-center gap-2">
                                                    <Loader2 className="h-4 w-4 animate-spin text-accent" />
                                                    <span className="text-sm text-muted-foreground">Flora pensando...</span>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </ScrollArea>

                        {/* Input Area */}
                        <div className="p-4 border-t">
                            <div className="flex gap-2">
                                <Input
                                    ref={inputRef}
                                    value={inputMessage}
                                    onChange={(e) => setInputMessage(e.target.value)}
                                    onKeyPress={handleKeyPress}
                                    placeholder="Digite sua pergunta ou use o microfone..."
                                    disabled={loading || isRecording}
                                    className="flex-1"
                                    data-testid="chat-input"
                                />
                                <Button 
                                    onClick={() => sendMessage()}
                                    disabled={loading || !inputMessage.trim() || isRecording}
                                    className="gap-2"
                                    data-testid="send-message-btn"
                                >
                                    {loading ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <Send className="h-4 w-4" />
                                    )}
                                    Enviar
                                </Button>
                            </div>
                            <p className="text-xs text-muted-foreground mt-2">
                                Enter para enviar • Clique em &quot;Falar&quot; ou diga &quot;Flora&quot;
                            </p>
                        </div>
                    </Card>
                </div>
            </div>
        </Layout>
    );
}

