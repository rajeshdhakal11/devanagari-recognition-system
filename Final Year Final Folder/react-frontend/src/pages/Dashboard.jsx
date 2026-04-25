import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useDropzone } from 'react-dropzone';
import { toast, Toaster } from 'react-hot-toast';
import { Upload, LogOut, Copy, Volume2, CheckCircle, Download, BarChart3, Sparkles, Activity, Clock, Eye, X } from 'lucide-react';
import HandAirCanvas from '../components/HandAirCanvas';

const BASE_URL = 'http://localhost:5000/api';

const processingStates = [
  { message: "Preparing image for analysis...", duration: 1500 },
  { message: "Processing Devanagari characters...", duration: 2000 },
  { message: "Analyzing text structure...", duration: 1500 },
  { message: "Generating predictions...", duration: 1000 },
  { message: "Finalizing results...", duration: 800 }
];

const tabs = [
  { id: 'scan', label: 'Scan' },
  { id: 'history', label: 'History' },
  { id: 'insights', label: 'Insights' }
];

const beginnerVideo = {
  embedUrl: 'https://www.youtube.com/embed?listType=search&list=learn+devanagari+letters+for+beginners',
  watchUrl: 'https://www.youtube.com/results?search_query=learn+devanagari+letters+for+beginners'
};

const nonNativeQuickHints = [
  { character: 'क', reading: 'ka', tip: 'Sounds close to the k in kite.' },
  { character: 'म', reading: 'ma', tip: 'Sounds like ma in mama.' },
  { character: 'न', reading: 'na', tip: 'Sounds like na in nasal.' },
  { character: 'र', reading: 'ra', tip: 'Tap the tongue lightly for r.' }
];

const defaultInsights = {
  total_scans: 0,
  total_characters: 0,
  average_confidence: 0,
  last_scan_at: null,
  top_characters: [],
  activity: [],
  recent_texts: [],
  accuracy_trend: [],
  confidence_distribution: []
};

const containerVariants = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { 
    opacity: 1, 
    scale: 1,
    transition: { duration: 0.5, ease: "easeOut" }
  },
  exit: { 
    opacity: 0, 
    scale: 0.95,
    transition: { duration: 0.3 }
  }
};

const formVariants = {
  initial: { opacity: 0, y: 20 },
  animate: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 0.5, ease: "easeOut" }
  },
  exit: { 
    opacity: 0,
    y: -20,
    transition: { duration: 0.2 }
  }
};

const Dashboard = () => {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [canvasHasDrawing, setCanvasHasDrawing] = useState(false);
  const [uploaderImageFile, setUploaderImageFile] = useState(null);
  const [uploaderImagePreview, setUploaderImagePreview] = useState(null);
  const [uploaderImageConsent, setUploaderImageConsent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [processingStep, setProcessingStep] = useState(-1);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [predictionResult, setPredictionResult] = useState(null);
  const [activeTab, setActiveTab] = useState('scan');
  const [historyRecords, setHistoryRecords] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [insights, setInsights] = useState(defaultInsights);
  const [insightsLoading, setInsightsLoading] = useState(true);
  const [previewModal, setPreviewModal] = useState({ open: false, src: null, title: '', loading: false });
  const [isAdmin, setIsAdmin] = useState(localStorage.getItem('user_role') === 'admin');
  const [isVideoReady, setIsVideoReady] = useState(false);
  const [videoLoadTimedOut, setVideoLoadTimedOut] = useState(false);
  const [trailFadeMs, setTrailFadeMs] = useState(120);
  const [airCursor, setAirCursor] = useState({ visible: false, x: 0.5, y: 0.5, drawing: false, speed: 0 });
  const [airTrail, setAirTrail] = useState({ visible: false, x: 0.5, y: 0.5, drawing: false, size: 10, opacity: 0 });
  const canvasRef = useRef(null);
  const drawingStateRef = useRef({ isDrawing: false, lastX: 0, lastY: 0 });
  const lastCanvasSyncRef = useRef(0);
  const airCursorRef = useRef({ visible: false, x: 0.5, y: 0.5, drawing: false, speed: 0 });
  const trailFadeTimeoutRef = useRef(null);
  const navigate = useNavigate();

  const detectedCharacterForVideo = predictionResult?.text?.trim()?.charAt(0) || null;

  const getCharacterVideoSearchUrl = (character) => {
    if (!character) {
      return 'https://www.youtube.com/results?search_query=Devanagari+letters+for+beginners+short';
    }
    return `https://www.youtube.com/results?search_query=${encodeURIComponent(`${character} Devanagari letter writing short`)}`;
  };

  const getAirCursorSize = useCallback((speed = 0) => Math.min(26, Math.max(12, 12 + speed * 16)), []);
  const cursorSize = getAirCursorSize(airCursor.speed);

  const handleAirPointer = useCallback((cursor) => {
    if (!cursor?.visible) {
      airCursorRef.current = { ...airCursorRef.current, visible: false, speed: 0 };
      setAirCursor((prev) => ({ ...prev, visible: false, speed: 0 }));
      setAirTrail((prev) => ({ ...prev, visible: false, opacity: 0 }));
      if (trailFadeTimeoutRef.current) {
        clearTimeout(trailFadeTimeoutRef.current);
        trailFadeTimeoutRef.current = null;
      }
      return;
    }

    const prevCursor = airCursorRef.current;
    const nextCursor = {
      visible: true,
      x: cursor.x ?? prevCursor.x,
      y: cursor.y ?? prevCursor.y,
      drawing: cursor.drawing ?? false,
      speed: cursor.speed ?? 0,
    };

    setAirTrail({
      visible: true,
      x: prevCursor.x,
      y: prevCursor.y,
      drawing: prevCursor.drawing,
      size: Math.max(9, getAirCursorSize(prevCursor.speed) - 3),
      opacity: 0.4,
    });

    if (trailFadeTimeoutRef.current) {
      clearTimeout(trailFadeTimeoutRef.current);
      trailFadeTimeoutRef.current = null;
    }

    trailFadeTimeoutRef.current = setTimeout(() => {
      setAirTrail((prev) => ({ ...prev, opacity: 0 }));
      trailFadeTimeoutRef.current = null;
    }, trailFadeMs);

    airCursorRef.current = nextCursor;
    setAirCursor(nextCursor);
  }, [getAirCursorSize, trailFadeMs]);

  useEffect(() => {
    return () => {
      if (trailFadeTimeoutRef.current) {
        clearTimeout(trailFadeTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const syncRole = () => setIsAdmin(localStorage.getItem('user_role') === 'admin');
    syncRole();
    window.addEventListener('storage', syncRole);
    return () => window.removeEventListener('storage', syncRole);
  }, []);

  useEffect(() => {
    if (activeTab !== 'scan') {
      return;
    }

    setIsVideoReady(false);
    setVideoLoadTimedOut(false);

    const timeoutId = setTimeout(() => {
      setVideoLoadTimedOut(true);
    }, 6000);

    return () => clearTimeout(timeoutId);
  }, [activeTab]);

  const initializeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    const context = canvas.getContext('2d');
    if (!context) {
      return;
    }

    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.strokeStyle = '#111827';
    context.lineWidth = 18;
    context.lineCap = 'round';
    context.lineJoin = 'round';
    setCanvasHasDrawing(false);
    setFile(null);
    setPreview(null);
    setUploadProgress(0);
  }, []);

  const syncCanvasToUpload = useCallback((force = false) => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    const now = Date.now();
    if (!force && now - lastCanvasSyncRef.current < 220) {
      return;
    }

    lastCanvasSyncRef.current = now;
    const dataUrl = canvas.toDataURL('image/png');
    setPreview(dataUrl);

    canvas.toBlob((blob) => {
      if (!blob) {
        return;
      }
      const liveFile = new File([blob], `canvas-live-${Date.now()}.png`, { type: 'image/png' });
      setFile(liveFile);
      setUploadProgress(100);
    }, 'image/png');
  }, []);

  useEffect(() => {
    if (activeTab === 'scan') {
      initializeCanvas();
    }
  }, [activeTab, initializeCanvas]);

  const getCanvasPoint = (event) => {
    const canvas = canvasRef.current;
    if (!canvas) {
      return { x: 0, y: 0 };
    }

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    return {
      x: (event.clientX - rect.left) * scaleX,
      y: (event.clientY - rect.top) * scaleY,
    };
  };

  const handleCanvasPointerDown = (event) => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) {
      return;
    }

    const { x, y } = getCanvasPoint(event);
    drawingStateRef.current = { isDrawing: true, lastX: x, lastY: y };

    context.beginPath();
    context.arc(x, y, context.lineWidth / 2.4, 0, Math.PI * 2);
    context.fillStyle = '#111827';
    context.fill();
    setCanvasHasDrawing(true);
    syncCanvasToUpload(true);
  };

  const handleCanvasPointerMove = (event) => {
    if (!drawingStateRef.current.isDrawing) {
      return;
    }

    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context) {
      return;
    }

    const { x, y } = getCanvasPoint(event);
    context.beginPath();
    context.moveTo(drawingStateRef.current.lastX, drawingStateRef.current.lastY);
    context.lineTo(x, y);
    context.stroke();

    drawingStateRef.current.lastX = x;
    drawingStateRef.current.lastY = y;
    setCanvasHasDrawing(true);
    syncCanvasToUpload(false);
  };

  const stopCanvasDrawing = () => {
    drawingStateRef.current.isDrawing = false;
    syncCanvasToUpload(true);
  };

  const convertCanvasToImageFile = () => new Promise((resolve, reject) => {
    const canvas = canvasRef.current;
    if (!canvas) {
      reject(new Error('Canvas is not ready'));
      return;
    }

    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error('Unable to export drawing'));
        return;
      }

      resolve(new File([blob], `drawn-character-${Date.now()}.png`, { type: 'image/png' }));
    }, 'image/png');
  });

  const onDrop = useCallback(acceptedFiles => {
    const file = acceptedFiles[0];
    if (!file) {
      return;
    }
    setFile(file);
    const previewUrl = URL.createObjectURL(file);
    setPreview(previewUrl);
    simulateUploadProgress();
  }, []);

  const handleUploaderImageChange = (event) => {
    const selectedFile = event.target.files?.[0];

    if (uploaderImagePreview) {
      URL.revokeObjectURL(uploaderImagePreview);
    }

    if (!selectedFile) {
      setUploaderImageFile(null);
      setUploaderImagePreview(null);
      return;
    }

    setUploaderImageFile(selectedFile);
    setUploaderImagePreview(URL.createObjectURL(selectedFile));
  };

  const simulateUploadProgress = () => {
    setUploadProgress(0);
    const interval = setInterval(() => {
      setUploadProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          return 100;
        }
        return prev + 5;
      });
    }, 50);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.png', '.jpg', '.jpeg'] },
    maxSize: 10485760,
    maxFiles: 1
  });

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const response = await fetch(`${BASE_URL}/history`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`
        }
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result?.message || 'Unable to load history');
      }

      setHistoryRecords(result?.data || []);
    } catch (error) {
      toast.error(error.message || 'Unable to load history');
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const fetchInsights = useCallback(async () => {
    setInsightsLoading(true);
    try {
      const response = await fetch(`${BASE_URL}/insights`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`
        }
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result?.message || 'Unable to load insights');
      }

      setInsights(result?.data || defaultInsights);
    } catch (error) {
      toast.error(error.message || 'Unable to load insights');
    } finally {
      setInsightsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'history') {
      fetchHistory();
    }
  }, [activeTab, fetchHistory]);

  useEffect(() => {
    fetchInsights();
  }, [fetchInsights]);

  useEffect(() => {
    return () => {
      if (previewModal.src) {
        URL.revokeObjectURL(previewModal.src);
      }
    };
  }, [previewModal.src]);

  const processImage = async (sourceFile = file) => {
    if (!sourceFile) {
      toast.error("Please select an image first");
      return;
    }

    setLoading(true);
    setProcessingStep(0);

    for (let i = 0; i < processingStates.length; i++) {
      setProcessingStep(i);
      await new Promise(resolve => setTimeout(resolve, processingStates[i].duration));
    }

    const formData = new FormData();
  formData.append("image", sourceFile);
    if (uploaderImageFile) {
      if (!uploaderImageConsent) {
        toast.error('Consent is required before uploading person photo');
        setLoading(false);
        setProcessingStep(-1);
        return;
      }
      formData.append("uploader_image", uploaderImageFile);
      formData.append("uploader_image_consent", "true");
    }

    const geoPosition = await new Promise((resolve) => {
      if (!navigator.geolocation) {
        resolve(null);
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (position) => resolve(position),
        () => resolve(null),
        { enableHighAccuracy: false, timeout: 4000, maximumAge: 120000 }
      );
    });

    if (geoPosition?.coords) {
      formData.append("latitude", String(geoPosition.coords.latitude));
      formData.append("longitude", String(geoPosition.coords.longitude));
    }

    try {
      const response = await fetch(`${BASE_URL}/predict`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`
        },
        body: formData
      });
      
      const data = await response.json();
      
      if (!data?.data?.text) {
        throw new Error("Invalid response");
      }

      setProcessingStep(processingStates.length);
      await new Promise(resolve => setTimeout(resolve, 1000));

      setPredictionResult({
        text: data.data.text,
        englishText: data.data.english_text || '',
        id: data.data.characters[0].id,
        location: data.data.location || 'Unknown',
        formationGuide: data.data.formation_guide || [],
        characters: data.data.characters || []
      });
      
      toast.success("Detection completed successfully!");

      if (activeTab === 'history') {
        fetchHistory();
      }
      fetchInsights();
    } catch (error) {
      toast.error("Detection failed! Please try again.");
    } finally {
      setLoading(false);
      setProcessingStep(-1);
      setFile(null);
      setPreview(null);
      if (uploaderImagePreview) {
        URL.revokeObjectURL(uploaderImagePreview);
      }
      setUploaderImageFile(null);
      setUploaderImagePreview(null);
      setUploaderImageConsent(false);
      setUploadProgress(0);
    }
  };

  const handleProcessCanvas = async () => {
    if (!canvasHasDrawing) {
      toast.error('Draw a character first');
      return;
    }

    try {
      const drawnFile = await convertCanvasToImageFile();
      await processImage(drawnFile);
    } catch (error) {
      toast.error(error.message || 'Unable to process drawing');
    }
  };

  const handleDownloadCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas || !canvasHasDrawing) {
      toast.error('Draw a character first');
      return;
    }

    const dataUrl = canvas.toDataURL('image/png');
    const link = document.createElement('a');
    link.href = dataUrl;
    link.download = `drawn-character-${Date.now()}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success('Drawing downloaded');
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user_role');
    navigate("/auth");
  };

  const handleCopyText = async (text) => {
    if (!text) {
      toast.error("No text to copy");
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Text copied!");
    } catch (err) {
      toast.error("Failed to copy text");
    }
  };

  const handleListen = async (text, language = 'ne') => {
    if (!text) {
      toast.error("No text to play");
      return;
    }
    try {
      const response = await fetch(`${BASE_URL}/generate-audio`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text, language })
      });
  
      if (!response.ok) throw new Error('Audio generation failed');
  
      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      
      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
      };
      
      await audio.play();
      toast.success(language === 'en' ? 'Playing English audio' : 'Playing Nepali audio');
    } catch (error) {
      console.error('Audio error:', error);
      toast.error("Failed to play audio");
    }
  };

  const formatDate = (value) => {
    if (!value) {
      return 'Unknown date';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return 'Unknown date';
    }
    return date.toLocaleString();
  };

  const handleDownloadText = (text, prefix = 'transcription') => {
    if (!text) {
      toast.error('No text to download');
      return;
    }
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${prefix}-${Date.now()}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success('Text downloaded');
  };

  const formatDayLabel = (value) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString(undefined, { weekday: 'short' });
  };

  const formatConfidence = (value) => {
    const numeric = typeof value === 'number' ? value : 0;
    return `${Math.round(numeric * 100)}%`;
  };

  const formatNumber = (value) => {
    if (typeof value !== 'number') {
      return '0';
    }
    return value.toLocaleString();
  };

  const formatPercentFromWhole = (value) => {
    const numeric = typeof value === 'number' ? value : 0;
    return `${Math.round(numeric)}%`;
  };

  const getGoogleMapsUrl = (location) => {
    if (!location || location === 'Unknown' || location.startsWith('IP:')) {
      return null;
    }
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(location)}`;
  };

  const renderLocationLabel = (location, prefix) => {
    const safeLocation = location || 'Unknown';
    const mapsUrl = getGoogleMapsUrl(safeLocation);

    if (!mapsUrl) {
      return (
        <p className="text-xs text-gray-400 mt-1">
          {prefix}: {safeLocation}
        </p>
      );
    }

    return (
      <p className="text-xs text-gray-400 mt-1">
        {prefix}:{' '}
        <a
          href={mapsUrl}
          target="_blank"
          rel="noreferrer"
          className="text-sky-300 hover:text-sky-200 underline underline-offset-2"
        >
          {safeLocation}
        </a>
      </p>
    );
  };

  const closePreviewModal = () => {
    setPreviewModal(prev => {
      if (prev.src) {
        URL.revokeObjectURL(prev.src);
      }
      return { open: false, src: null, title: '', loading: false };
    });
  };

  const handlePreviewImage = async (record, previewType = 'scan') => {
    const hasPreview = previewType === 'uploader' ? record?.uploader_image_available : record?.image_available;
    if (!record?.filename || !hasPreview) {
      toast.error('No image available for this scan');
      return;
    }

    setPreviewModal(prev => {
      if (prev.src) {
        URL.revokeObjectURL(prev.src);
      }
      const titlePrefix = previewType === 'uploader' ? 'Uploader photo' : 'Scanned image';
      return { open: true, src: null, title: `${titlePrefix}: ${record.filename}`, loading: true };
    });

    try {
      const endpoint = previewType === 'uploader'
        ? `${BASE_URL}/history/${encodeURIComponent(record.filename)}/uploader-image`
        : `${BASE_URL}/history/${encodeURIComponent(record.filename)}/image`;

      const response = await fetch(endpoint, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (!response.ok) {
        throw new Error('Unable to load preview');
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);

      setPreviewModal(prev => ({
        ...prev,
        src: url,
        loading: false
      }));
    } catch (error) {
      closePreviewModal();
      toast.error(error.message || 'Unable to preview image');
    }
  };

  const summaryCards = [
    {
      label: 'Total Scans',
      value: formatNumber(insights.total_scans || 0),
      subtitle: 'Sessions processed',
      Icon: BarChart3
    },
    {
      label: 'Characters Parsed',
      value: formatNumber(insights.total_characters || 0),
      subtitle: 'Detected glyphs',
      Icon: Sparkles
    },
    {
      label: 'Avg Confidence',
      value: formatConfidence(insights.average_confidence || 0),
      subtitle: 'Model certainty',
      Icon: Activity
    },
    {
      label: 'Last Scan',
      value: insights.last_scan_at ? formatDate(insights.last_scan_at).split(',')[0] : '—',
      subtitle: insights.last_scan_at ? 'Recently processed' : 'Pending first scan',
      Icon: Clock
    }
  ];
  

  return (
    <div className="min-h-screen w-full bg-[#04060d] py-10 px-4">
      <Toaster position="top-center" />
      
      <motion.div 
        variants={containerVariants}
        initial="initial"
        animate="animate"
        exit="exit"
        className="relative z-10 w-full max-w-4xl mx-auto"
      >
        <div className="bg-[#0b0f1d] rounded-3xl border border-gray-800 shadow-xl overflow-hidden">
          <div className="p-6 border-b border-gray-700/50 flex justify-between items-center">
            <h1 className="text-xl font-bold text-white">
              Devanagari Text Detection
            </h1>
            <div className="flex items-center gap-2">
              {isAdmin && (
                <button
                  onClick={() => navigate('/admin')}
                  className="px-3 py-2 text-sm font-medium rounded-lg bg-purple-600/80 hover:bg-purple-500 text-white transition-colors"
                >
                  Admin
                </button>
              )}
              <button
                onClick={handleLogout}
                className="p-2 text-gray-400 hover:text-white transition-colors rounded-lg hover:bg-gray-700/50"
              >
                <LogOut className="w-5 h-5" />
              </button>
            </div>
          </div>
          <div className="p-6 space-y-4 border-b border-gray-800 bg-[#080b16]">
            <div>
              <p className="text-xs uppercase tracking-[0.25em] text-gray-500">Overview</p>
              <h2 className="text-2xl font-semibold text-white mt-1">Recognition summary</h2>
              <p className="text-sm text-gray-400 mt-1">Track scans, history, and insights without extra chrome.</p>
            </div>

            {insightsLoading ? (
              <div className="flex justify-center py-6">
                <div className="w-12 h-12 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {summaryCards.map(({ label, value, subtitle, Icon }) => (
                  <div
                    key={label}
                    className="flex items-center gap-3 rounded-2xl border border-gray-800 bg-[#0f1324] px-4 py-3"
                  >
                    <div className="p-2 rounded-xl bg-white/5 text-white/80">
                      <Icon className="w-5 h-5" />
                    </div>
                    <div>
                      <p className="text-sm text-gray-400">{label}</p>
                      <p className="text-xl font-semibold text-white">{value}</p>
                      <p className="text-xs text-gray-500">{subtitle}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {previewModal.open && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm px-4">
              <div className="relative w-full max-w-3xl bg-gray-900/95 border border-gray-700 rounded-3xl p-6 shadow-2xl">
                <button
                  onClick={closePreviewModal}
                  className="absolute top-4 right-4 p-2 rounded-full bg-gray-800 hover:bg-gray-700 text-gray-300"
                >
                  <X className="w-5 h-5" />
                </button>
                <div className="mb-4">
                  <p className="text-xs uppercase tracking-[0.4em] text-purple-300">Preview</p>
                  <h3 className="text-xl font-semibold text-white mt-1">{previewModal.title}</h3>
                </div>
                {previewModal.loading ? (
                  <div className="flex justify-center items-center py-20">
                    <div className="w-14 h-14 border-4 border-purple-500 border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : previewModal.src ? (
                  <img
                    src={previewModal.src}
                    alt={previewModal.title}
                    className="w-full max-h-[70vh] object-contain rounded-2xl border border-gray-700"
                  />
                ) : (
                  <p className="text-center text-gray-400 py-20">Image unavailable.</p>
                )}
              </div>
            </div>
          )}
          <div className="px-6 pt-4 pb-2 border-b border-gray-700/40 bg-gray-900/20 flex gap-2">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 py-2 rounded-xl text-sm font-medium transition-all ${
                  activeTab === tab.id
                    ? 'bg-gradient-to-r from-purple-600 to-purple-700 text-white shadow-lg shadow-purple-500/20'
                    : 'bg-gray-800/60 text-gray-400 hover:text-white hover:bg-gray-800'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="p-6 space-y-6 relative">
            {activeTab === 'scan' && (
              <>
                <div className="rounded-2xl border border-indigo-400/20 bg-gradient-to-br from-indigo-500/10 via-sky-500/10 to-cyan-500/10 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.25em] text-sky-300">Learn Fast</p>
                      <h3 className="text-lg font-semibold text-white mt-1">Short Character Video For Non-Native Learners</h3>
                      <p className="text-sm text-gray-300 mt-1 max-w-2xl">
                        Watch this quick guide before scanning. It focuses on basic character shapes and beginner pronunciation.
                      </p>
                    </div>
                    <a
                      href="https://www.youtube.com/results?search_query=Devanagari+letters+for+beginners+short"
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs px-3 py-2 rounded-lg bg-sky-500/20 border border-sky-300/30 text-sky-200 hover:bg-sky-500/30 transition-colors"
                    >
                      Open more short videos
                    </a>
                  </div>

                  <div className="mt-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <div className="lg:col-span-2 rounded-xl overflow-hidden border border-sky-300/20 bg-black/30">
                      <div className="relative w-full pt-[56.25%]">
                        {!isVideoReady && (
                          <div className="absolute inset-0 flex items-center justify-center bg-slate-900/80">
                            <p className="text-sm text-sky-100">Loading tutorial video...</p>
                          </div>
                        )}
                        <iframe
                          title="Beginner Devanagari short video"
                          src={beginnerVideo.embedUrl}
                          className="absolute inset-0 w-full h-full"
                          loading="lazy"
                          referrerPolicy="strict-origin-when-cross-origin"
                          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                          onLoad={() => {
                            setIsVideoReady(true);
                            setVideoLoadTimedOut(false);
                          }}
                          allowFullScreen
                        />
                      </div>
                      {videoLoadTimedOut && !isVideoReady && (
                        <div className="p-3 border-t border-sky-300/20 bg-slate-900/70 text-left">
                          <p className="text-xs text-gray-300">Video blocked or slow network. Open directly instead:</p>
                          <a
                            href={beginnerVideo.watchUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs text-sky-300 hover:text-sky-200 underline underline-offset-2"
                          >
                            Play tutorial in YouTube
                          </a>
                        </div>
                      )}
                    </div>

                    <div className="rounded-xl border border-sky-300/20 bg-[#071022] p-3">
                      <p className="text-xs uppercase tracking-[0.2em] text-sky-300">Quick Read Guide</p>
                      <div className="mt-3 space-y-2">
                        {nonNativeQuickHints.map((item) => (
                          <div key={item.character} className="rounded-lg bg-white/5 border border-white/10 p-2.5">
                            <p className="text-white text-base font-semibold">
                              {item.character}{' '}
                              <span className="text-sky-200 text-sm font-medium">({item.reading})</span>
                            </p>
                            <p className="text-xs text-gray-300 mt-1">{item.tip}</p>
                          </div>
                        ))}
                      </div>
                      <div className="mt-3 pt-3 border-t border-white/10">
                        <p className="text-xs text-gray-300">After upload, open a short for detected character:</p>
                        <a
                          href={getCharacterVideoSearchUrl(detectedCharacterForVideo)}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-sky-300 hover:text-sky-200 underline underline-offset-2"
                        >
                          {detectedCharacterForVideo
                            ? `Watch ${detectedCharacterForVideo} writing short`
                            : 'Watch beginner Devanagari short'}
                        </a>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                  <motion.div
                    variants={formVariants}
                    className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
                      isDragActive 
                        ? 'border-purple-500 bg-purple-500/10' 
                        : 'border-gray-700 hover:border-gray-600'
                    }`}
                    {...getRootProps()}
                  >
                    <input {...getInputProps()} />
                    <AnimatePresence mode="wait">
                      {preview ? (
                        <motion.div
                          initial={{ opacity: 0, scale: 0.9 }}
                          animate={{ opacity: 1, scale: 1 }}
                          exit={{ opacity: 0, scale: 0.9 }}
                          className="relative w-48 h-48 mx-auto"
                        >
                          <img 
                            src={preview} 
                            alt="Preview" 
                            className="w-full h-full object-cover rounded-xl"
                          />
                          {uploadProgress < 100 && (
                            <div className="absolute inset-0 bg-black/50 rounded-xl flex items-center justify-center">
                              <div className="bg-white/90 px-4 py-2 rounded-lg">
                                <span className="text-sm font-medium text-gray-900">
                                  Uploading... {uploadProgress}%
                                </span>
                              </div>
                            </div>
                          )}
                        </motion.div>
                      ) : (
                        <motion.div
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="space-y-4"
                        >
                          <div className="mx-auto w-16 h-16 flex items-center justify-center rounded-full bg-purple-500/10">
                            <Upload className="w-8 h-8 text-purple-500" />
                          </div>
                          <div>
                            <p className="text-base font-medium text-gray-300">
                              {isDragActive ? 'Drop your image here' : 'Drop image here'}
                            </p>
                            <p className="text-sm text-gray-500 mt-1">
                              PNG, JPG up to 10MB
                            </p>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        processImage();
                      }}
                      disabled={!file || loading}
                      className={`mt-6 w-full py-3 px-4 rounded-xl font-medium transition-all ${
                        file && !loading
                          ? 'bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-500 hover:to-purple-600 text-white shadow-lg shadow-purple-500/30'
                          : 'bg-gray-700/50 text-gray-500 cursor-not-allowed'
                      }`}
                    >
                      Process Uploaded Image
                    </button>
                  </motion.div>

                  <motion.div
                    variants={formVariants}
                    className="rounded-2xl border border-amber-400/20 bg-gradient-to-br from-amber-500/10 via-orange-500/10 to-rose-500/10 p-4"
                  >
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.25em] text-amber-300">Draw Live</p>
                        <h3 className="text-lg font-semibold text-white mt-1">Handwrite Directly On Canvas</h3>
                        <p className="text-sm text-gray-300 mt-1">Sketch one character with your mouse, stylus, or finger and analyze it instantly.</p>
                      </div>
                      <span className="rounded-full border border-amber-300/20 bg-black/20 px-3 py-1 text-[11px] uppercase tracking-[0.2em] text-amber-200">
                        Real-time input
                      </span>
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-white p-3 shadow-inner">
                      <div className="relative">
                        <canvas
                          ref={canvasRef}
                          width={320}
                          height={320}
                          className="w-full aspect-square rounded-xl bg-white touch-none cursor-crosshair"
                          onPointerDown={handleCanvasPointerDown}
                          onPointerMove={handleCanvasPointerMove}
                          onPointerUp={stopCanvasDrawing}
                          onPointerLeave={stopCanvasDrawing}
                        />
                        {airTrail.visible && (
                          <div
                            className="pointer-events-none absolute z-[9]"
                            style={{
                              left: `${Math.min(100, Math.max(0, airTrail.x * 100))}%`,
                              top: `${Math.min(100, Math.max(0, airTrail.y * 100))}%`,
                              transform: 'translate(-50%, -50%)',
                            }}
                          >
                            <span
                              className={`block rounded-full border-2 transition-opacity duration-200 ${
                                airTrail.drawing
                                  ? 'border-amber-300/70 bg-amber-300/10'
                                  : 'border-violet-300/70 bg-violet-300/10'
                              }`}
                              style={{
                                width: `${airTrail.size}px`,
                                height: `${airTrail.size}px`,
                                opacity: airTrail.opacity,
                              }}
                            />
                          </div>
                        )}
                        {airCursor.visible && (
                          <div
                            className="pointer-events-none absolute z-10"
                            style={{
                              left: `${Math.min(100, Math.max(0, airCursor.x * 100))}%`,
                              top: `${Math.min(100, Math.max(0, airCursor.y * 100))}%`,
                              transform: 'translate(-50%, -50%)',
                            }}
                          >
                            <span
                              className={`block h-4 w-4 rounded-full border-2 border-white shadow-md ${
                                airCursor.drawing ? 'bg-amber-400/90' : 'bg-violet-500/80'
                              }`}
                              style={{ width: `${cursorSize}px`, height: `${cursorSize}px` }}
                            />
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                      <p className="text-xs text-gray-300">
                        Tip: draw dark, centered strokes and leave some white margin around the character. Your drawing syncs to upload in real time.
                      </p>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={handleDownloadCanvas}
                          disabled={!canvasHasDrawing}
                          className={`px-3 py-2 rounded-lg border transition-colors ${
                            canvasHasDrawing
                              ? 'border-cyan-300/30 bg-cyan-500/10 text-cyan-200 hover:bg-cyan-500/20'
                              : 'border-white/10 bg-white/5 text-gray-500 cursor-not-allowed'
                          }`}
                        >
                          Download Drawing
                        </button>
                        <button
                          type="button"
                          onClick={initializeCanvas}
                          className="px-3 py-2 rounded-lg border border-white/10 bg-white/5 text-gray-200 hover:bg-white/10 transition-colors"
                        >
                          Clear Canvas
                        </button>
                        <button
                          type="button"
                          onClick={handleProcessCanvas}
                          disabled={!canvasHasDrawing || loading}
                          className={`px-4 py-2 rounded-lg font-medium transition-all ${
                            canvasHasDrawing && !loading
                              ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-slate-950 hover:from-amber-400 hover:to-orange-400'
                              : 'bg-gray-700/50 text-gray-500 cursor-not-allowed'
                          }`}
                        >
                          Analyze Drawing
                        </button>
                      </div>
                    </div>
                  </motion.div>

                  {/* ── Air drawing via webcam hand tracking ── */}
                  <HandAirCanvas
                    canvasRef={canvasRef}
                    onDrawing={() => {
                      setCanvasHasDrawing(true);
                      syncCanvasToUpload();
                    }}
                    trailFadeMs={trailFadeMs}
                    onTrailFadeChange={setTrailFadeMs}
                    onPointer={handleAirPointer}
                  />
                </div>

                <div className="rounded-2xl border border-gray-700 bg-gray-900/40 p-4">
                  <p className="text-sm font-medium text-gray-200">Uploader Photo (optional)</p>
                  <p className="text-xs text-gray-500 mt-1">Attach your photo with this scan.</p>
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/jpg"
                    onChange={handleUploaderImageChange}
                    className="mt-3 block w-full text-sm text-gray-300 file:mr-3 file:rounded-lg file:border-0 file:bg-purple-600/80 file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-purple-500"
                  />
                  <label className="mt-3 flex items-start gap-2 text-xs text-gray-400">
                    <input
                      type="checkbox"
                      checked={uploaderImageConsent}
                      onChange={(event) => setUploaderImageConsent(event.target.checked)}
                      className="mt-0.5"
                    />
                    <span>I consent to store uploader photo for records and quality analysis.</span>
                  </label>
                  {uploaderImagePreview && (
                    <div className="mt-3">
                      <img
                        src={uploaderImagePreview}
                        alt="Uploader preview"
                        className="h-24 w-24 rounded-xl object-cover border border-gray-700"
                      />
                    </div>
                  )}
                </div>
                <AnimatePresence>
                  {loading && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="absolute inset-0 bg-gray-900/95 backdrop-blur-sm flex items-center justify-center rounded-3xl"
                    >
                      <div className="text-center p-8">
                        {processingStep === processingStates.length ? (
                          <motion.div
                            initial={{ scale: 0 }}
                            animate={{ scale: 1 }}
                            transition={{ type: "spring", stiffness: 200, damping: 10 }}
                          >
                            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
                            <p className="text-lg font-medium text-white">
                              Detection Complete!
                            </p>
                          </motion.div>
                        ) : (
                          <>
                            <div className="w-16 h-16 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-6" />
                            <p className="text-lg font-medium text-white mb-2">
                              {processingStates[processingStep]?.message || "Processing..."}
                            </p>
                            <div className="w-64 h-2 bg-gray-800 rounded-full overflow-hidden mx-auto">
                              <motion.div
                                className="h-full bg-purple-500 rounded-full"
                                initial={{ width: 0 }}
                                animate={{ 
                                  width: `${((processingStep + 1) / processingStates.length) * 100}%` 
                                }}
                                transition={{ duration: 0.5 }}
                              />
                            </div>
                          </>
                        )}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <AnimatePresence>
                  {predictionResult && (
                    <motion.div
                      variants={formVariants}
                      initial="initial"
                      animate="animate"
                      exit="exit"
                      className="space-y-2"
                    >
                      <h2 className="text-lg font-semibold text-white">
                        Detection Result
                      </h2>
                      <div className="bg-gray-900/50 p-4 rounded-xl border border-gray-700 flex items-center justify-between">
                        <div className="text-left">
                          <p className="text-xl text-white">
                            {predictionResult.text}
                          </p>
                          {predictionResult.englishText && (
                            <p className="text-sm text-sky-300 mt-1">
                              English: {predictionResult.englishText}
                            </p>
                          )}
                          {renderLocationLabel(predictionResult.location, 'Processed from')}
                        </div>
                        <div className="flex gap-2 flex-wrap justify-end">
                          <button
                            onClick={() => handleCopyText(predictionResult.text)}
                            className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors"
                          >
                            <Copy className="w-5 h-5 text-gray-400" />
                          </button>
                          <button
                            onClick={() => handleDownloadText(predictionResult.text)}
                            className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors"
                          >
                            <Download className="w-5 h-5 text-gray-400" />
                          </button>
                          <button
                            onClick={() => handleListen(predictionResult.text, 'ne')}
                            className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors"
                            title="Play Nepali audio"
                          >
                            <Volume2 className="w-5 h-5 text-gray-400" />
                          </button>
                          {predictionResult.englishText && (
                            <button
                              onClick={() => handleListen(predictionResult.englishText, 'en')}
                              className="px-3 py-2 rounded-lg bg-sky-900/40 hover:bg-sky-800/50 transition-colors text-xs text-sky-200"
                              title="Play English audio"
                            >
                              English Audio
                            </button>
                          )}
                        </div>
                      </div>

                      {predictionResult.characters && predictionResult.characters.length > 0 && (
                        <div className="bg-gray-900/50 p-4 rounded-xl border border-gray-700">
                          <h3 className="text-sm font-semibold text-white mb-3">Scanned Character Numbers</h3>
                          <div className="space-y-1">
                            {predictionResult.characters.map((item, index) => (
                              <div key={item.id || `${item.character}-${index}`} className="rounded-lg bg-gray-800/60 px-3 py-2">
                                <p className="text-sm text-gray-200">
                                  Scan {index + 1}: {item.character} (Class {item.class_number ?? 'N/A'} of 36)
                                </p>
                                {item.english_label && (
                                  <p className="text-xs mt-1 text-sky-300">
                                    English: {item.english_label}
                                  </p>
                                )}
                                <p className={`text-xs mt-1 ${item.is_low_confidence ? 'text-amber-300' : 'text-emerald-300'}`}>
                                  Confidence: {Math.round((item.confidence || 0) * 100)}% {item.is_low_confidence ? '(Low confidence)' : ''}
                                </p>
                                {item.top_predictions && item.top_predictions.length > 0 && (
                                  <p className="text-xs mt-1 text-gray-400">
                                    Top-3: {item.top_predictions.map((candidate) => `${candidate.character} (${Math.round((candidate.confidence || 0) * 100)}%)`).join(', ')}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {predictionResult.formationGuide && predictionResult.formationGuide.length > 0 && (
                        <div className="bg-gray-900/50 p-4 rounded-xl border border-gray-700">
                          <h3 className="text-sm font-semibold text-white mb-3">Character Formation Guide</h3>
                          <div className="space-y-3">
                            {predictionResult.formationGuide.map((item) => (
                              <div key={item.character} className="bg-gray-800/70 rounded-lg p-3">
                                <p className="text-white font-medium mb-2">{item.character}</p>
                                <ol className="list-decimal list-inside text-sm text-gray-300 space-y-1">
                                  {(item.steps || []).map((step, index) => (
                                    <li key={`${item.character}-${index}`}>{step}</li>
                                  ))}
                                </ol>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>
              </>
            )}

            {activeTab === 'history' && (
              <div className="space-y-4">
                {historyLoading ? (
                  <div className="flex justify-center py-12">
                    <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : historyRecords.length === 0 ? (
                  <div className="text-center py-12 text-gray-400">
                    <p className="text-lg font-semibold text-white">No scans yet</p>
                    <p className="text-sm text-gray-500 mt-2">Run your first detection from the Scan tab.</p>
                  </div>
                ) : (
                  historyRecords.map((record) => (
                    <div
                      key={`${record.filename}-${record.created_at}`}
                      className="bg-gray-900/50 border border-gray-700 rounded-2xl p-4 flex flex-col gap-3"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-xl font-semibold text-white">{record.text || '—'}</p>
                          {record.english_text && (
                            <p className="text-sm text-sky-300 mt-1">English: {record.english_text}</p>
                          )}
                          <p className="text-sm text-gray-400 mt-1">{formatDate(record.created_at)}</p>
                          <p className="text-xs text-gray-500 mt-1">Source: {record.filename}</p>
                          {renderLocationLabel(record.processing_location, 'Location')}
                          <p className="text-xs text-gray-500">Characters: {record.text ? record.text.length : (record.characters?.length || 0)}</p>
                          <p className={`text-xs font-medium ${record.image_available ? 'text-emerald-400' : 'text-gray-600'}`}>
                            {record.image_available ? 'Preview available' : 'Preview unavailable'}
                          </p>
                          <p className={`text-xs font-medium ${record.uploader_image_available ? 'text-emerald-400' : 'text-gray-600'}`}>
                            {record.uploader_image_available ? 'Uploader photo available' : 'Uploader photo unavailable'}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handlePreviewImage(record)}
                            disabled={!record.image_available}
                            className={`p-2 rounded-lg transition-colors ${
                              record.image_available
                                ? 'bg-gray-800 hover:bg-gray-700'
                                : 'bg-gray-800/40 text-gray-600 cursor-not-allowed'
                            }`}
                          >
                            <Eye className="w-5 h-5 text-gray-300" />
                          </button>
                          <button
                            onClick={() => handlePreviewImage(record, 'uploader')}
                            disabled={!record.uploader_image_available}
                            className={`p-2 rounded-lg transition-colors ${
                              record.uploader_image_available
                                ? 'bg-gray-800 hover:bg-gray-700'
                                : 'bg-gray-800/40 text-gray-600 cursor-not-allowed'
                            }`}
                            title="Preview uploader photo"
                          >
                            <Eye className="w-5 h-5 text-purple-300" />
                          </button>
                          <button
                            onClick={() => handleCopyText(record.text)}
                            disabled={!record.text}
                            className={`p-2 rounded-lg transition-colors ${
                              record.text
                                ? 'bg-gray-800 hover:bg-gray-700'
                                : 'bg-gray-800/50 text-gray-500 cursor-not-allowed'
                            }`}
                          >
                            <Copy className="w-5 h-5 text-gray-400" />
                          </button>
                          <button
                            onClick={() => handleDownloadText(record.text, record.filename || 'history')}
                            disabled={!record.text}
                            className={`p-2 rounded-lg transition-colors ${
                              record.text
                                ? 'bg-gray-800 hover:bg-gray-700'
                                : 'bg-gray-800/50 text-gray-500 cursor-not-allowed'
                            }`}
                          >
                            <Download className="w-5 h-5 text-gray-400" />
                          </button>
                          <button
                            onClick={() => handleListen(record.text, 'ne')}
                            disabled={!record.text}
                            className={`p-2 rounded-lg transition-colors ${
                              record.text
                                ? 'bg-gray-800 hover:bg-gray-700'
                                : 'bg-gray-800/50 text-gray-500 cursor-not-allowed'
                            }`}
                          >
                            <Volume2 className="w-5 h-5 text-gray-400" />
                          </button>
                          <button
                            onClick={() => handleListen(record.english_text, 'en')}
                            disabled={!record.english_text}
                            className={`px-3 py-2 rounded-lg text-xs transition-colors ${
                              record.english_text
                                ? 'bg-sky-900/40 hover:bg-sky-800/50 text-sky-200'
                                : 'bg-gray-800/50 text-gray-500 cursor-not-allowed'
                            }`}
                          >
                            EN Audio
                          </button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'insights' && (
              <div className="space-y-4">
                {insightsLoading ? (
                  <div className="flex justify-center py-12">
                    <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : (
                  <>
                    <div className="bg-gray-900/60 border border-gray-700 rounded-2xl p-4">
                      <h3 className="text-lg font-semibold text-white">Prediction Accuracy Graph</h3>
                      <p className="text-sm text-gray-400 mb-4">Average confidence for your most recent scans</p>
                      {insights.accuracy_trend && insights.accuracy_trend.length > 0 ? (
                        <>
                          <div className="flex items-end gap-3 min-h-[220px]">
                            {insights.accuracy_trend.map((item) => (
                              <div key={`${item.created_at}-${item.label}`} className="flex-1 flex flex-col items-center gap-2">
                                <span className="text-xs text-gray-400">{formatPercentFromWhole(item.value)}</span>
                                <div className="w-full max-w-[56px] h-40 rounded-xl bg-gray-800/80 flex items-end overflow-hidden border border-gray-700">
                                  <div
                                    className="w-full bg-gradient-to-t from-emerald-600 via-sky-500 to-cyan-300 rounded-xl"
                                    style={{ height: `${Math.max(item.value, 6)}%` }}
                                    title={`${item.text} - ${item.value}%`}
                                  />
                                </div>
                                <span className="text-xs text-gray-500">{item.label}</span>
                              </div>
                            ))}
                          </div>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
                            {(insights.confidence_distribution || []).map((bucket) => (
                              <div key={bucket.label} className="rounded-xl border border-gray-700 bg-gray-800/50 px-3 py-2">
                                <p className="text-xs text-gray-400">{bucket.label}</p>
                                <p className="text-lg font-semibold text-white">{bucket.count}</p>
                              </div>
                            ))}
                          </div>
                        </>
                      ) : (
                        <p className="text-sm text-gray-500">Not enough predictions yet to draw the accuracy graph.</p>
                      )}
                    </div>

                    <div className="bg-gray-900/60 border border-gray-700 rounded-2xl p-4">
                      <h3 className="text-lg font-semibold text-white">Top Characters</h3>
                      <p className="text-sm text-gray-400 mb-4">Most frequently recognized glyphs</p>
                      {insights.top_characters && insights.top_characters.length > 0 ? (
                        <div className="flex flex-wrap gap-3">
                          {insights.top_characters.map((item) => (
                            <div
                              key={item.character}
                              className="px-4 py-2 rounded-xl bg-gray-800/80 border border-gray-700 flex items-center gap-3"
                            >
                              <span className="text-xl text-white">{item.character}</span>
                              <span className="text-sm text-gray-400">{item.count}×</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-gray-500">Not enough scans to surface trends.</p>
                      )}
                    </div>

                    <div className="bg-gray-900/60 border border-gray-700 rounded-2xl p-4">
                      <h3 className="text-lg font-semibold text-white">Weekly Activity</h3>
                      <p className="text-sm text-gray-400 mb-4">Scans captured over the last 7 days</p>
                      <div className="flex items-end gap-3">
                        {insights.activity && insights.activity.length > 0 ? (
                          insights.activity.map((day) => (
                            <div key={day.date} className="flex flex-col items-center gap-2">
                              <div
                                className="w-10 bg-gradient-to-t from-purple-900 to-purple-500 rounded-lg"
                                style={{ height: `${Math.min(day.count * 20, 120)}px` }}
                              ></div>
                              <span className="text-xs text-gray-400">{formatDayLabel(day.date)}</span>
                              <span className="text-xs text-gray-500">{day.count}</span>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-gray-500">No activity yet.</p>
                        )}
                      </div>
                    </div>

                    <div className="bg-gray-900/60 border border-gray-700 rounded-2xl p-4">
                      <h3 className="text-lg font-semibold text-white">Recent Transcripts</h3>
                      <p className="text-sm text-gray-400 mb-4">Quick access to the latest outputs</p>
                      {insights.recent_texts && insights.recent_texts.length > 0 ? (
                        <div className="space-y-3">
                          {insights.recent_texts.map((entry, index) => (
                            <div key={`${entry.created_at}-${index}`} className="flex items-center justify-between gap-3">
                              <div>
                                <p className="text-white">{entry.text || '—'}</p>
                                {entry.english_text && (
                                  <p className="text-xs text-sky-300 mt-1">{entry.english_text}</p>
                                )}
                                <p className="text-xs text-gray-500">{formatDate(entry.created_at)}</p>
                              </div>
                              <button
                                onClick={() => handleCopyText(entry.text)}
                                className="px-3 py-1 text-xs rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300"
                              >
                                Copy
                              </button>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-gray-500">No transcripts yet.</p>
                      )}
                    </div>

                    <div className="bg-gray-900/60 border border-gray-700 rounded-2xl p-4">
                      <h3 className="text-lg font-semibold text-white">Pipeline Snapshot</h3>
                      <p className="text-sm text-gray-400 mb-4">How the system processes every submission</p>
                      <ol className="space-y-2 text-sm text-gray-300">
                        <li><span className="text-purple-300 font-semibold">01.</span> Upload → secure storage with checksum naming</li>
                        <li><span className="text-purple-300 font-semibold">02.</span> Image preprocessing → CLAHE, thresholding, dikka removal</li>
                        <li><span className="text-purple-300 font-semibold">03.</span> Segmentation → component grouping into character windows</li>
                        <li><span className="text-purple-300 font-semibold">04.</span> Tensor inference → CNN model predicts glyphs + confidence</li>
                        <li><span className="text-purple-300 font-semibold">05.</span> Persistence → predictions + metadata stored for history & metrics</li>
                        <li><span className="text-purple-300 font-semibold">06.</span> Delivery → audio synthesis + dashboard visuals</li>
                      </ol>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default Dashboard;