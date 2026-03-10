import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { ScrollArea } from './ui/scroll-area';
import {
    MessageCircle, X, Send, Mic, MicOff, Volume2, VolumeX, Loader2
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function FloatingFloraChat() {
    const { user } = useAuth();
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState([]);
    const [inputMessage, setInputMessage] = useState('');
    const [loading, setLoading] = useState(false);
    const [voiceEnabled, setVoiceEnabled] = useState(true);
    const [isRecording, setIsRecording] = useState(false);
    const scrollRef = useRef(null);
    const inputRef = useRef(null);
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const audioRef = useRef(null);

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages]);

    // Initial greeting
    useEffect(() => {
        if (isOpen && messages.length === 0) {
            const greeting = "Olá! Sou a Flora, sua assistente. Como posso ajudá-lo?";
            setMessages([{
                role: 'assistant',
                content: greeting,
                timestamp: new Date().toISOString()
            }]);
            if (voiceEnabled) {
                speakText(greeting);
            }
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen]);

    const speakText = async (text) => {
        try {
            const response = await axios.post(
                `${API}/voice/speak?text=${encodeURIComponent(text.substring(0, 500))}`
            );

            if (response.data.audio) {
                const audio = new Audio(`data:audio/mp3;base64,${response.data.audio}`);
                audio.play().catch(e => console.error('Audio play error:', e));
            }
        } catch (error) {
            console.error('TTS error:', error);
        }
    };

    const sendMessage = async () => {
        const text = inputMessage.trim();
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
                message: text
            });

            const assistantMessage = {
                role: 'assistant',
                content: response.data.response,
                timestamp: new Date().toISOString()
            };
            setMessages(prev => [...prev, assistantMessage]);

            if (voiceEnabled) {
                speakText(response.data.response);
            }
        } catch (error) {
            toast.error('Erro ao enviar mensagem');
            setMessages(prev => prev.slice(0, -1));
        } finally {
            setLoading(false);
            inputRef.current?.focus();
        }
    };

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
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
        } catch (error) {
            toast.error('Erro ao acessar microfone');
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        }
    };

    const processVoiceCommand = async (audioBlob) => {
        setLoading(true);

        try {
            const formData = new FormData();
            formData.append('audio', audioBlob, 'command.webm');

            const response = await axios.post(`${API}/voice/command`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            const { transcribed_text, response_text } = response.data;

            if (transcribed_text) {
                setMessages(prev => [...prev, {
                    role: 'user',
                    content: `🎤 ${transcribed_text}`,
                    timestamp: new Date().toISOString()
                }]);
            }

            if (response_text) {
                setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: response_text,
                    timestamp: new Date().toISOString()
                }]);

                if (voiceEnabled) {
                    speakText(response_text);
                }
            }
        } catch (error) {
            toast.error('Erro ao processar comando');
        } finally {
            setLoading(false);
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    if (!user) return null;

    return (
        <>
            {/* Floating Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={`fixed bottom-6 right-6 rounded-full p-4 shadow-lg transition-all ${
                    isOpen
                        ? 'bg-red-500 hover:bg-red-600'
                        : 'bg-blue-500 hover:bg-blue-600'
                } text-white z-40`}
                aria-label="Abrir Flora"
            >
                {isOpen ? (
                    <X size={24} />
                ) : (
                    <MessageCircle size={24} />
                )}
            </button>

            {/* Chat Window */}
            {isOpen && (
                <div className="fixed bottom-24 right-6 w-80 bg-white rounded-lg shadow-2xl flex flex-col z-40 border border-gray-200" style={{ height: '500px' }}>
                    {/* Header */}
                    <div className="bg-gradient-to-r from-blue-500 to-blue-600 text-white p-4 rounded-t-lg">
                        <h3 className="font-bold text-lg">💬 Flora</h3>
                        <p className="text-sm text-blue-100">Sua assistente de campanha</p>
                    </div>

                    {/* Messages */}
                    <ScrollArea ref={scrollRef} className="flex-1 p-4 space-y-3">
                        {messages.map((msg, idx) => (
                            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div
                                    className={`max-w-xs px-4 py-2 rounded-lg ${
                                        msg.role === 'user'
                                            ? 'bg-blue-500 text-white rounded-br-none'
                                            : 'bg-gray-200 text-gray-900 rounded-bl-none'
                                    }`}
                                >
                                    <p className="text-sm">{msg.content}</p>
                                </div>
                            </div>
                        ))}
                        {loading && (
                            <div className="flex justify-start">
                                <div className="bg-gray-200 text-gray-900 px-4 py-2 rounded-lg rounded-bl-none">
                                    <Loader2 size={16} className="animate-spin" />
                                </div>
                            </div>
                        )}
                    </ScrollArea>

                    {/* Input Area */}
                    <div className="border-t p-3 space-y-2">
                        {/* Voice Controls */}
                        <div className="flex gap-2 justify-between">
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setVoiceEnabled(!voiceEnabled)}
                                className="flex-1"
                            >
                                {voiceEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
                            </Button>
                            <Button
                                size="sm"
                                variant={isRecording ? 'destructive' : 'outline'}
                                onClick={isRecording ? stopRecording : startRecording}
                                className="flex-1"
                            >
                                {isRecording ? <MicOff size={16} /> : <Mic size={16} />}
                            </Button>
                        </div>

                        {/* Text Input */}
                        <div className="flex gap-2">
                            <Input
                                ref={inputRef}
                                value={inputMessage}
                                onChange={(e) => setInputMessage(e.target.value)}
                                onKeyPress={handleKeyPress}
                                placeholder="Digite sua mensagem..."
                                className="flex-1 text-sm"
                                disabled={loading}
                            />
                            <Button
                                size="sm"
                                onClick={sendMessage}
                                disabled={loading || !inputMessage.trim()}
                                className="px-3"
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
