import { useState, useEffect, useRef } from 'react';
import Layout from '../components/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import axios from 'axios';
import { toast } from 'sonner';
import { 
    Bot, Send, Loader2, Trash2, AlertTriangle, 
    FileText, BarChart3, Shield, Sparkles, MessageSquare,
    ChevronRight, RefreshCw
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
    const [messages, setMessages] = useState([]);
    const [inputMessage, setInputMessage] = useState('');
    const [loading, setLoading] = useState(false);
    const [loadingHistory, setLoadingHistory] = useState(true);
    const [alerts, setAlerts] = useState([]);
    const [sessionId, setSessionId] = useState(null);
    const scrollRef = useRef(null);
    const inputRef = useRef(null);

    useEffect(() => {
        fetchChatHistory();
    }, []);

    useEffect(() => {
        // Auto scroll to bottom
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

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

    const sendMessage = async (messageText = null) => {
        const text = messageText || inputMessage.trim();
        if (!text) return;

        // Add user message immediately
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

            // Add assistant response
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
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Erro ao enviar mensagem');
            // Remove user message on error
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

    const formatMessage = (content) => {
        // Convert markdown-like formatting to HTML
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
                            Assistente IA Eleitoral
                        </h1>
                        <p className="text-muted-foreground mt-1">
                            Tire dúvidas sobre sua campanha e receba orientações sobre conformidade
                        </p>
                    </div>
                    <div className="flex gap-2">
                        <Button 
                            variant="outline" 
                            size="sm" 
                            onClick={fetchChatHistory}
                            className="gap-2"
                        >
                            <RefreshCw className="h-4 w-4" />
                            Atualizar
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

                {/* Main Chat Area */}
                <div className="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-4 min-h-0">
                    {/* Quick Actions Sidebar */}
                    <Card className="lg:col-span-1 h-fit">
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

                    {/* Chat Window */}
                    <Card className="lg:col-span-3 flex flex-col min-h-0">
                        <CardHeader className="pb-3 border-b">
                            <div className="flex items-center gap-2">
                                <MessageSquare className="h-5 w-5 text-accent" />
                                <CardTitle className="text-base">Conversa</CardTitle>
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
                                    <Bot className="h-12 w-12 text-muted-foreground/50 mb-4" />
                                    <p className="text-muted-foreground">
                                        Olá! Sou seu assistente eleitoral.
                                    </p>
                                    <p className="text-sm text-muted-foreground/70 mt-1">
                                        Pergunte sobre sua campanha, gastos ou regras do TSE.
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
                                                        <span className="text-xs font-medium text-accent">Assistente IA</span>
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
                                                    <span className="text-sm text-muted-foreground">Pensando...</span>
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
                                    placeholder="Digite sua pergunta sobre a campanha..."
                                    disabled={loading}
                                    className="flex-1"
                                    data-testid="chat-input"
                                />
                                <Button 
                                    onClick={() => sendMessage()}
                                    disabled={loading || !inputMessage.trim()}
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
                                Pressione Enter para enviar • O assistente tem acesso aos dados da sua campanha
                            </p>
                        </div>
                    </Card>
                </div>
            </div>
        </Layout>
    );
}
