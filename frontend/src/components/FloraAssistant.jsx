import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { ScrollArea } from './ui/scroll-area';
import {
    MessageCircle,
    X,
    Send,
    Mic,
    MicOff,
    Volume2,
    VolumeX,
    Loader2,
    Sparkles
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const DEFAULT_HELP =
    'Posso ajudar com receitas, despesas, contratos, pagamentos e relatorios. O que voce deseja fazer agora?';

const FAQ = [
    {
        match: ['fundo partidario', 'fundo de partido'],
        answer:
            'O fundo partidario e um recurso publico destinado aos partidos para custear atividades e campanhas, seguindo as regras do TSE.'
    },
    {
        match: ['fundo eleitoral', 'fefc', 'financiamento publico'],
        answer:
            'O fundo eleitoral (FEFC) e um recurso publico para financiar campanhas, distribuido conforme regras do TSE.'
    },
    {
        match: ['spce', 'pre check', 'pre-check'],
        answer:
            'O SPCE e o sistema de prestacao de contas eleitoral. O pre-check ajuda a identificar pendencias antes de enviar.'
    },
    {
        match: ['limite de gastos', 'teto de gastos', 'limite tse'],
        answer:
            'O limite de gastos e definido pelo TSE e depende do cargo e do municipio. O sistema ajuda a monitorar esse teto.'
    },
    {
        match: ['documento fiscal', 'nota fiscal', 'comprovante'],
        answer:
            'Para cada despesa, mantenha o documento fiscal ou comprovante valido. Isso evita glosas na prestacao de contas.'
    },
    {
        match: ['como cadastrar despesa', 'lancar despesa', 'registrar despesa'],
        answer:
            'Para cadastrar uma despesa, abra Despesas, clique em Nova Despesa e preencha fornecedor, valor, data e comprovante.'
    }
];

const ACTIONS = [
    {
        match: ['lancar despesa', 'lancar uma despesa', 'nova despesa', 'cadastrar despesa', 'registrar despesa', 'cadastrar gasto', 'preciso cadastrar um gasto'],
        response: 'Claro, vou abrir o formulario de despesa para voce. Deseja cadastrar agora?',
        route: '/despesas'
    },
    {
        match: ['gerar contrato e despesa vinculada', 'contrato com despesa vinculada', 'criar contrato e despesa', 'gerar contrato com despesa'],
        response: 'Vou abrir contratos e preparar a despesa vinculada. Posso seguir com o formulario agora?',
        route: '/contratos'
    },
    {
        match: ['criar contrato', 'novo contrato', 'gerar contrato', 'abrir contratos', 'contrato'],
        response: 'Vou abrir a aba de contratos para criar um novo contrato. Posso seguir?',
        route: '/contratos'
    },
    {
        match: ['fazer pagamento', 'realizar pagamento', 'pagamento', 'abrir pagamentos'],
        response: 'Vou abrir a area de pagamentos para voce. Quer agendar agora?',
        route: '/pagamentos'
    },
    {
        match: ['abrir receitas', 'lancar receita', 'nova receita', 'cadastrar receita'],
        response: 'Ok, vou abrir receitas para voce. Deseja cadastrar uma nova entrada?',
        route: '/receitas'
    },
    {
        match: ['ver relatorios', 'abrir relatorios', 'relatorios'],
        response: 'Certo, vou abrir relatorios para voce. Quer um resumo agora?',
        route: '/relatorios'
    },
    {
        match: ['abrir configuracoes', 'configuracoes', 'ajustar campanha'],
        response: 'Vou abrir configuracoes para voce. Precisa atualizar algum dado?',
        route: '/configuracoes'
    },
    {
        match: ['conformidade', 'pre-check', 'pre check', 'spce'],
        response: 'Vou abrir a area de conformidade para voce. Posso iniciar a verificacao?',
        route: '/conformidade'
    },
    {
        match: ['assinar contrato', 'assinar um contrato', 'assinatura de contrato'],
        response: 'Vou abrir contratos para voce assinar. Quer que eu abra o contrato pendente?',
        route: '/contratos'
    },
    {
        match: ['enviar documentos', 'anexar documentos', 'subir documentos', 'enviar anexos'],
        response: 'Vou abrir contratos para voce anexar documentos. Quer ver pendencias?',
        route: '/contratos'
    },
    {
        match: ['importar extrato', 'extrato bancario', 'extratos bancarios'],
        response: 'Vou abrir extratos bancarios para voce. Quer importar agora?',
        route: '/extratos'
    },
    {
        match: ['assistente', 'assistente ia'],
        response: 'Abrindo o painel completo da assistente. Quer ver o historico?',
        route: '/assistente'
    },
    {
        match: ['inicio', 'dashboard', 'painel'],
        response: 'Voltando para o inicio. Posso ajudar em mais alguma coisa?',
        route: '/dashboard'
    }
];

const normalizeText = (text) =>
    text
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .replace(/[^a-z0-9\s]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();

const findFAQ = (text) => {
    const normalized = normalizeText(text);
    return FAQ.find((item) => item.match.some((keyword) => normalized.includes(keyword)));
};

const findAction = (text) => {
    const normalized = normalizeText(text);
    return ACTIONS.find((action) => action.match.some((keyword) => normalized.includes(keyword)));
};

export function FloraAssistant() {
    const navigate = useNavigate();
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([]);
    const [inputMessage, setInputMessage] = useState('');
    const [loading, setLoading] = useState(false);
    const [voiceEnabled, setVoiceEnabled] = useState(true);
    const [isListening, setIsListening] = useState(false);
    const [speechSupported, setSpeechSupported] = useState(false);
    const [wakeEnabled] = useState(true);
    const [wakeStatus, setWakeStatus] = useState('inativo');
    const scrollRef = useRef(null);
    const inputRef = useRef(null);
    const recognitionRef = useRef(null);
    const sendMessageRef = useRef(null);
    const audioRef = useRef(null);

    const greeting = useMemo(
        () =>
            'Ola, sou a Flora. Como posso te ajudar hoje? Posso abrir despesas, contratos, pagamentos ou receitas.',
        []
    );

    const openPanel = useCallback(() => {
        setIsOpen(true);
    }, []);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    useEffect(() => {
        if (!isOpen || messages.length > 0) return;
        const welcome = {
            role: 'assistant',
            content: greeting,
            timestamp: new Date().toISOString()
        };
        setMessages([welcome]);
        if (voiceEnabled) {
            speak(greeting);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen]);

    const speak = useCallback(async (text) => {
        if (!voiceEnabled || !text) return;
        try {
            const response = await axios.post(
                `${API}/voice/speak?text=${encodeURIComponent(text.substring(0, 500))}`
            );
            const audioBase64 = response.data?.audio;
            if (audioBase64) {
                if (audioRef.current) {
                    audioRef.current.pause();
                    audioRef.current.currentTime = 0;
                }
                const audio = new Audio(`data:audio/mp3;base64,${audioBase64}`);
                audioRef.current = audio;
                audio.play().catch(() => {});
            }
        } catch (error) {
            // Fail silently if TTS is unavailable
        }
    }, [voiceEnabled]);

    const addAssistantMessage = useCallback((content) => {
        const assistantMessage = {
            role: 'assistant',
            content,
            timestamp: new Date().toISOString()
        };
        setMessages((prev) => [...prev, assistantMessage]);
        speak(content);
    }, [speak]);

    const handleWakeTranscript = useCallback((transcript) => {
        const normalized = normalizeText(transcript);
        if (!normalized.includes('flora')) return;

        const parts = normalized.split('flora');
        const afterWake = (parts[1] || '').trim();
        openPanel();
        if (afterWake) {
            sendMessageRef.current?.(afterWake);
            return;
        }
        addAssistantMessage('Ola, em que posso te ajudar agora?');
    }, [addAssistantMessage, openPanel]);

    useEffect(() => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        setSpeechSupported(Boolean(SpeechRecognition));
        if (SpeechRecognition) {
            const recognition = new SpeechRecognition();
            recognition.lang = 'pt-BR';
            recognition.interimResults = true;
            recognition.maxAlternatives = 1;
            recognition.continuous = true;
            recognition.onresult = (event) => {
                const lastResult = event.results?.[event.results.length - 1];
                const transcript = lastResult?.[0]?.transcript;
                if (transcript) {
                    handleWakeTranscript(transcript);
                }
            };
            recognition.onend = () => {
                setIsListening(false);
                if (wakeEnabled) {
                    try {
                        recognition.start();
                        setIsListening(true);
                        setWakeStatus('ouvindo');
                    } catch {
                        setWakeStatus('inativo');
                    }
                }
            };
            recognition.onerror = () => {
                setIsListening(false);
                setWakeStatus('inativo');
            };
            recognitionRef.current = recognition;
        }
    }, [handleWakeTranscript, wakeEnabled]);

    const executeCommand = useCallback((action) => {
        if (action?.route) {
            navigate(action.route);
        }
    }, [navigate]);

    const sendMessage = useCallback(async (textInput) => {
        const text = (textInput ? textInput : inputMessage).trim();
        if (!text) return;

        const userMessage = {
            role: 'user',
            content: text,
            timestamp: new Date().toISOString()
        };
        setMessages((prev) => [...prev, userMessage]);
        setInputMessage('');

        const faq = findFAQ(text);
        if (faq) {
            addAssistantMessage(`${faq.answer} ${DEFAULT_HELP}`);
            return;
        }

        const action = findAction(text);
        if (action) {
            addAssistantMessage(action.response);
            executeCommand(action);
            return;
        }

        if (normalizeText(text).includes('ajuda') || normalizeText(text).includes('me ajude')) {
            addAssistantMessage(DEFAULT_HELP);
            return;
        }

        setLoading(true);
        try {
            const response = await axios.post(`${API}/ai/chat`, { message: text });
            const reply = response.data?.response;
            if (reply) {
                addAssistantMessage(reply);
            } else {
                addAssistantMessage(`Nao entendi completamente. ${DEFAULT_HELP}`);
            }
        } catch (error) {
            addAssistantMessage(`Estou com instabilidade agora. ${DEFAULT_HELP}`);
        } finally {
            setLoading(false);
            inputRef.current?.focus();
        }
    }, [
        inputMessage,
        addAssistantMessage,
        executeCommand
    ]);

    useEffect(() => {
        sendMessageRef.current = sendMessage;
    }, [sendMessage]);

    const handleKeyPress = (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    };

    const startWakeListening = useCallback(async () => {
        if (!speechSupported || !recognitionRef.current) return;
        try {
            await navigator.mediaDevices.getUserMedia({ audio: true });
            recognitionRef.current.start();
            setIsListening(true);
            setWakeStatus('ouvindo');
        } catch {
            setWakeStatus('bloqueado');
        }
    }, [speechSupported]);

    const stopWakeListening = useCallback(() => {
        if (recognitionRef.current) {
            recognitionRef.current.stop();
        }
        setIsListening(false);
        setWakeStatus('inativo');
    }, []);

    useEffect(() => {
        if (!speechSupported) return;
        if (wakeEnabled) {
            startWakeListening();
            return;
        }
        stopWakeListening();
    }, [wakeEnabled, speechSupported, startWakeListening, stopWakeListening]);

    return (
        <>
            <button
                onClick={() => setIsOpen((prev) => !prev)}
                className={`fixed bottom-6 right-6 rounded-full p-4 shadow-lg transition-all z-50 ${
                    isOpen ? 'bg-slate-700 hover:bg-slate-800' : 'bg-blue-600 hover:bg-blue-700'
                } text-white`}
                aria-label="Abrir Flora"
                data-testid="flora-floating-btn"
            >
                {isOpen ? <X size={22} /> : <MessageCircle size={22} />}
            </button>

            {isOpen && (
                <div
                    className="fixed bottom-24 right-6 w-[360px] max-w-[92vw] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col z-50"
                    style={{ height: '560px' }}
                    data-testid="flora-assistant-panel"
                >
                    <div className="rounded-t-2xl bg-gradient-to-r from-blue-600 to-blue-500 text-white p-4">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
                                <Sparkles className="h-5 w-5" />
                            </div>
                            <div>
                                <p className="font-semibold">Flora</p>
                                <p className="text-xs text-blue-100">Assistente da campanha</p>
                            </div>
                            <div className="ml-auto flex items-center gap-2">
                                <Button
                                    size="icon"
                                    variant="ghost"
                                    onClick={() => setVoiceEnabled((prev) => !prev)}
                                    className="text-white hover:bg-white/20"
                                    aria-label="Alternar voz"
                                >
                                    {voiceEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
                                </Button>
                            </div>
                        </div>
                        {!speechSupported && (
                            <p className="text-[11px] text-blue-100 mt-2">Microfone indisponivel neste navegador.</p>
                        )}
                        {speechSupported && (
                            <p className="text-[11px] text-blue-100 mt-2">
                                Escuta por \"flora\": {wakeStatus}
                            </p>
                        )}
                    </div>

                    <ScrollArea ref={scrollRef} className="flex-1 p-4 space-y-4">
                        {messages.map((msg, idx) => (
                            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div
                                    className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm ${
                                        msg.role === 'user'
                                            ? 'bg-blue-600 text-white rounded-br-none'
                                            : 'bg-slate-100 text-slate-900 rounded-bl-none'
                                    }`}
                                >
                                    {msg.content}
                                </div>
                            </div>
                        ))}
                        {loading && (
                            <div className="flex justify-start">
                                <div className="bg-slate-100 text-slate-900 px-4 py-2 rounded-2xl rounded-bl-none">
                                    <Loader2 size={16} className="animate-spin" />
                                </div>
                            </div>
                        )}
                    </ScrollArea>

                    <div className="border-t border-slate-200 p-3">
                        <div className="flex items-center gap-2">
                            <div className="flex-1 flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-2">
                                <Input
                                    ref={inputRef}
                                    value={inputMessage}
                                    onChange={(event) => setInputMessage(event.target.value)}
                                    onKeyPress={handleKeyPress}
                                    placeholder="Digite seu pedido..."
                                    className="flex-1 text-sm border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
                                    disabled={loading}
                                />
                                {speechSupported && (
                                    <div
                                        className={`h-9 w-9 rounded-full border flex items-center justify-center transition ${
                                            wakeStatus === 'ouvindo'
                                                ? 'border-emerald-400 text-emerald-600 shadow-[0_0_0_4px_rgba(16,185,129,0.15)]'
                                                : wakeStatus === 'bloqueado'
                                                    ? 'border-amber-300 text-amber-500'
                                                    : 'border-slate-200 text-slate-500'
                                        }`}
                                        aria-label="Escuta por voz ativa"
                                        title="Escuta ativa por voz: diga Flora"
                                    >
                                        <Mic size={16} />
                                    </div>
                                )}
                            </div>
                            <Button
                                onClick={() => sendMessage()}
                                disabled={loading || !inputMessage.trim()}
                                className="h-10 w-10 rounded-full bg-blue-600 hover:bg-blue-700 p-0"
                                aria-label="Enviar mensagem"
                            >
                                <Send size={16} />
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
