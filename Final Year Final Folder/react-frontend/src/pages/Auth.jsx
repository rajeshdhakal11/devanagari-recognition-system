import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Toaster, toast } from 'react-hot-toast';
import { Shield, EyeOff, Eye, Calendar, UserRound, Mail, Lock, ChevronLeft, ChevronRight, Camera } from 'lucide-react';
import { signin, signup, getUsernameSuggestions, requestSignupOtp, verifySignupOtp, faceSignin, setupFaceLogin } from '../utils/api';

const Auth = () => {
  const [isSignup, setIsSignup] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    email: '',
    phone_number: '',
    password: '',
    username: '',
    first_name: '',
    last_name: '',
    date_of_birth: '',
    identifier: '',
    otp: ''
  });
  const [otpSent, setOtpSent] = useState(false);
  const [otpVerified, setOtpVerified] = useState(false);
  const [otpLoading, setOtpLoading] = useState(false);
  const [usernameEdited, setUsernameEdited] = useState(false);
  const [suggestedUsername, setSuggestedUsername] = useState('');
  const [capturedFaceImage, setCapturedFaceImage] = useState('');
  const [cameraActive, setCameraActive] = useState(false);
  const [faceActionLoading, setFaceActionLoading] = useState(false);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [calendarView, setCalendarView] = useState(() => {
    const base = new Date();
    return {
      month: base.getMonth(),
      year: base.getFullYear() - 16
    };
  });
  const calendarWrapperRef = useRef(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const monthNames = useMemo(() => (
    ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  ), []);
  const weekDays = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
  const {
    yearsOptions,
    minYear,
    maxYear,
    cutoffIso
  } = useMemo(() => {
    const today = new Date();
    const computedMaxYear = today.getFullYear() - 16;
    const computedMinYear = today.getFullYear() - 60;
    const cutoff = new Date(today);
    cutoff.setFullYear(computedMaxYear);
    const formatIso = (date) => (
      `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
    );

    const years = [];
    for (let year = computedMaxYear; year >= computedMinYear; year -= 1) {
      years.push(year);
    }

    return {
      yearsOptions: years,
      minYear: computedMinYear,
      maxYear: computedMaxYear,
      cutoffIso: formatIso(cutoff)
    };
  }, []);
  const calendarDays = useMemo(() => {
    const { month, year } = calendarView;
    const totalDays = new Date(year, month + 1, 0).getDate();
    const firstWeekday = new Date(year, month, 1).getDay();
    const slots = [];

    for (let i = 0; i < firstWeekday; i += 1) {
      slots.push(null);
    }

    for (let day = 1; day <= totalDays; day += 1) {
      const iso = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      slots.push({ day, iso });
    }

    return slots;
  }, [calendarView]);

  const shiftCalendarMonth = (direction) => {
    setCalendarView((prev) => {
      let nextMonth = prev.month + direction;
      let nextYear = prev.year;

      if (nextMonth < 0) {
        nextMonth = 11;
        nextYear -= 1;
      } else if (nextMonth > 11) {
        nextMonth = 0;
        nextYear += 1;
      }

      if (nextYear > maxYear || nextYear < minYear) {
        return prev;
      }

      return { month: nextMonth, year: nextYear };
    });
  };

  const handleDateSelect = (isoDate) => {
    if (isoDate > cutoffIso) {
      return;
    }
    setForm((prev) => ({ ...prev, date_of_birth: isoDate }));
    setCalendarOpen(false);
  };

  const selectedDobLabel = useMemo(() => {
    if (!form.date_of_birth) {
      return 'Select date';
    }
    const parsed = new Date(`${form.date_of_birth}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) {
      return 'Select date';
    }
    return parsed.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
  }, [form.date_of_birth]);

  const navigate = useNavigate();

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));

    if (name === 'username') {
      if (value.trim().length === 0) {
        setUsernameEdited(false);
        setSuggestedUsername('');
      } else {
        setUsernameEdited(true);
      }
    }

    if (name === 'phone_number') {
      setOtpSent(false);
      setOtpVerified(false);
    }
  };

  const handleRequestOtp = async () => {
    const phoneNumber = (form.phone_number || '').trim();
    if (!phoneNumber) {
      toast.error('Enter phone number first');
      return;
    }

    setOtpLoading(true);
    try {
      const otpResponse = await requestSignupOtp({ phone_number: phoneNumber });
      setOtpSent(true);
      setOtpVerified(false);
      toast.success('OTP sent');

      const devOtp = otpResponse?.data?.dev_otp;
      const deliveryChannel = otpResponse?.data?.delivery_channel;
      if (devOtp && deliveryChannel === 'development-fallback') {
        toast.success(`Dev OTP: ${devOtp}`, { duration: 8000 });
      }
    } catch (error) {
      toast.error(error.response?.data?.message || 'Unable to send OTP');
    } finally {
      setOtpLoading(false);
    }
  };

  const handleVerifyOtp = async () => {
    const phoneNumber = (form.phone_number || '').trim();
    const otp = (form.otp || '').trim();

    if (!phoneNumber || !otp) {
      toast.error('Enter phone number and OTP');
      return;
    }

    setOtpLoading(true);
    try {
      await verifySignupOtp({ phone_number: phoneNumber, otp });
      setOtpVerified(true);
      toast.success('OTP verified');
    } catch (error) {
      setOtpVerified(false);
      toast.error(error.response?.data?.message || 'OTP verification failed');
    } finally {
      setOtpLoading(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);

    if (isSignup && !form.date_of_birth) {
      toast.error('Select your complete date of birth');
      setLoading(false);
      return;
    }
    if (isSignup && !otpVerified) {
      toast.error('Verify OTP before creating account');
      setLoading(false);
      return;
    }
    try {
      if (isSignup) {
        await signup(form);
        toast.success('Account created');
        setOtpSent(false);
        setOtpVerified(false);
        setForm((prev) => ({ ...prev, otp: '' }));
        setIsSignup(false);
      } else {
        const loginPayload = {
          identifier: (form.identifier || form.email || '').trim(),
          password: form.password
        };
        await signin(loginPayload);
        toast.success('Welcome back');
        navigate('/dashboard');
      }
    } catch (error) {
      toast.error(error.response?.data?.message || 'Unable to complete request');
    } finally {
      setLoading(false);
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  };

  const startCamera = async () => {
    try {
      stopCamera();
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCameraActive(true);
      toast.success('Camera ready');
    } catch (error) {
      toast.error('Unable to access camera');
      setCameraActive(false);
    }
  };

  const captureFace = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth || !video.videoHeight) {
      toast.error('Camera is not ready');
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext('2d');

    if (!context) {
      toast.error('Unable to capture face image');
      return;
    }

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageDataUrl = canvas.toDataURL('image/jpeg', 0.9);
    setCapturedFaceImage(imageDataUrl);
    toast.success('Face image captured');
  };

  const handleFaceSignin = async () => {
    const identifier = (form.identifier || form.email || '').trim();
    if (!identifier) {
      toast.error('Enter email or username first');
      return;
    }
    if (!capturedFaceImage) {
      toast.error('Capture your face image first');
      return;
    }

    setFaceActionLoading(true);
    try {
      await faceSignin({ identifier, image: capturedFaceImage });
      toast.success('Face login successful');
      navigate('/dashboard');
    } catch (error) {
      toast.error(error.response?.data?.message || 'Face login failed');
    } finally {
      setFaceActionLoading(false);
    }
  };

  const handleSetupFaceLogin = async () => {
    const identifier = (form.identifier || form.email || '').trim();
    if (!identifier || !form.password) {
      toast.error('Enter identifier and password to enable face login');
      return;
    }
    if (!capturedFaceImage) {
      toast.error('Capture your face image first');
      return;
    }

    setFaceActionLoading(true);
    try {
      await setupFaceLogin({
        identifier,
        password: form.password,
        image: capturedFaceImage,
      });
      toast.success('Face login enabled for your account');
    } catch (error) {
      toast.error(error.response?.data?.message || 'Face setup failed');
    } finally {
      setFaceActionLoading(false);
    }
  };

  useEffect(() => {
    if (!isSignup) {
      setUsernameEdited(false);
      setSuggestedUsername('');
      setCalendarOpen(false);
      setOtpSent(false);
      setOtpVerified(false);
      setForm((prev) => ({ ...prev, otp: '' }));
    }
  }, [isSignup]);

  useEffect(() => () => stopCamera(), []);

  useEffect(() => {
    if (!isSignup || usernameEdited) {
      return;
    }

    const first = form.first_name.trim();
    const last = form.last_name.trim();

    if (!first || !last) {
      return;
    }

    let isActive = true;

    const fetchSuggestion = async () => {
      try {
        const suggestions = await getUsernameSuggestions({
          first_name: first,
          last_name: last
        });

        if (!isActive || !Array.isArray(suggestions) || suggestions.length === 0) {
          return;
        }

        const primary = suggestions[0];
        setSuggestedUsername(primary);
        setForm((prev) => prev.username === primary ? prev : { ...prev, username: primary });
      } catch (error) {
        if (isActive) {
          setSuggestedUsername('');
        }
        console.error('Failed to fetch username suggestion', error);
      }
    };

    fetchSuggestion();

    return () => {
      isActive = false;
    };
  }, [form.first_name, form.last_name, isSignup, usernameEdited]);

  useEffect(() => {
    if (!form.date_of_birth) {
      return;
    }
    const [year, month] = form.date_of_birth.split('-').map(Number);
    if (!year || !month) {
      return;
    }
    setCalendarView((prev) => (
      prev.year === year && prev.month === month - 1
        ? prev
        : { month: month - 1, year }
    ));
  }, [form.date_of_birth]);

  useEffect(() => {
    if (!calendarOpen) {
      return undefined;
    }

    const handleClickOutside = (event) => {
      if (calendarWrapperRef.current && !calendarWrapperRef.current.contains(event.target)) {
        setCalendarOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [calendarOpen]);

  useEffect(() => {
    setCalendarView((prev) => {
      let nextYear = prev.year;
      if (prev.year > maxYear) {
        nextYear = maxYear;
      } else if (prev.year < minYear) {
        nextYear = minYear;
      }

      return nextYear === prev.year ? prev : { ...prev, year: nextYear };
    });
  }, [maxYear, minYear]);

  const renderInput = ({ label, icon, rightSlot = null, helperText, ...rest }) => {
    const inputProps = { autoComplete: 'off', ...rest };
    return (
      <label className="space-y-2 text-sm text-slate-400">
        <span className="font-medium text-slate-200">{label}</span>
        <div className="flex items-center gap-3 rounded-2xl border border-red-900/40 bg-[#1a0b0e] px-4 py-3">
          {icon && (
            <span className="flex h-5 w-5 items-center justify-center text-red-300/70">
              {icon}
            </span>
          )}
          <input
            {...inputProps}
            className="flex-1 bg-transparent text-red-50 placeholder:text-red-200/40 focus:outline-none"
          />
          {rightSlot}
        </div>
        {helperText && (
          <p className="text-xs text-red-200/55">{helperText}</p>
        )}
      </label>
    );
  };

  const renderDOB = () => {
    const isPrevDisabled = calendarView.year <= minYear && calendarView.month === 0;
    const isNextDisabled = calendarView.year >= maxYear && calendarView.month === 11;

    return (
      <div ref={calendarWrapperRef} className="relative">
        <label className="space-y-2 text-sm text-slate-400">
          <span className="font-medium text-slate-200">Date of birth</span>
          <button
            type="button"
            onClick={() => setCalendarOpen((open) => !open)}
            aria-haspopup="dialog"
            aria-expanded={calendarOpen}
            className="flex w-full items-center justify-between rounded-2xl border border-red-900/40 bg-[#1a0b0e] px-4 py-4 text-left"
          >
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-red-200/55">Calendar</p>
              <p className="text-lg font-semibold text-red-50">{selectedDobLabel}</p>
            </div>
            <Calendar className="h-5 w-5 text-red-300/70" />
          </button>

          {calendarOpen && (
            <div className="absolute inset-x-0 top-full z-20 mt-3 rounded-2xl border border-red-900/40 bg-[#12060a] p-4 shadow-2xl">
              <div className="flex items-center justify-between gap-3 border-b border-white/5 pb-3">
                <button
                  type="button"
                  onClick={() => shiftCalendarMonth(-1)}
                  disabled={isPrevDisabled}
                  className={`rounded-full border border-white/10 p-2 text-slate-300 transition ${isPrevDisabled ? 'cursor-not-allowed opacity-30' : 'hover:border-white/30 hover:text-white'}`}
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-white">{monthNames[calendarView.month]}</span>
                  <select
                    className="rounded-xl border border-white/10 bg-transparent px-2 py-1 text-sm text-slate-100 focus:outline-none"
                    value={calendarView.year}
                    onChange={(event) => setCalendarView((prev) => ({ ...prev, year: Number(event.target.value) }))}
                  >
                    {yearsOptions.map((year) => (
                      <option key={year} value={year} className="bg-slate-900 text-slate-100">
                        {year}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="button"
                  onClick={() => shiftCalendarMonth(1)}
                  disabled={isNextDisabled}
                  className={`rounded-full border border-white/10 p-2 text-slate-300 transition ${isNextDisabled ? 'cursor-not-allowed opacity-30' : 'hover:border-white/30 hover:text-white'}`}
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>

              <div className="mt-3 grid grid-cols-7 gap-1 text-center text-xs uppercase tracking-[0.2em] text-slate-500">
                {weekDays.map((day, index) => (
                  <span key={`${day}-${index}`}>{day}</span>
                ))}
              </div>

              <div className="mt-2 grid grid-cols-7 gap-1 text-center text-sm">
                {calendarDays.map((entry, index) => (
                  entry ? (
                    <button
                      type="button"
                      key={entry.iso}
                      disabled={entry.iso > cutoffIso}
                      onClick={() => handleDateSelect(entry.iso)}
                      className={`h-9 w-full rounded-full transition ${
                        entry.iso === form.date_of_birth
                          ? 'bg-red-500 text-white font-semibold'
                          : 'text-slate-200 hover:bg-red-500/15'
                      } ${entry.iso > cutoffIso ? 'cursor-not-allowed text-slate-600 opacity-30 hover:bg-transparent' : ''}`}
                    >
                      {entry.day}
                    </button>
                  ) : (
                    <span key={`empty-${index}`} className="h-9 w-full" />
                  )
                ))}
              </div>
            </div>
          )}
        </label>
      </div>
    );
  };

  return (
    <div className="min-h-screen w-full bg-[#140507] text-slate-100 flex items-center justify-center px-4 py-10">
      <Toaster position="top-center" />

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md space-y-8"
      >
        <div className="text-center space-y-3">
          <span className="inline-flex items-center gap-2 rounded-full border border-red-900/40 px-4 py-1 text-xs uppercase tracking-[0.35em] text-red-200/70">
            <Shield className="h-4 w-4" />
            Console
          </span>
          <div>
            <h1 className="text-3xl font-semibold text-red-50">
              {isSignup ? 'Create an account' : 'Sign in to continue'}
            </h1>
            <p className="text-sm text-red-200/70">
              Minimal screen aligned with the dashboard palette.
            </p>
          </div>
        </div>

        <div className="rounded-[28px] border border-red-900/40 bg-[#22090d] p-8 shadow-lg shadow-black/20">
          <div className="mb-6 flex rounded-2xl bg-[#2a0d13] p-1">
            <button
              type="button"
              onClick={() => setIsSignup(false)}
              className={`flex-1 rounded-2xl py-2 text-sm font-medium transition ${
                !isSignup ? 'bg-red-500 text-white shadow' : 'text-red-200/70'
              }`}
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => setIsSignup(true)}
              className={`flex-1 rounded-2xl py-2 text-sm font-medium transition ${
                isSignup ? 'bg-red-500 text-white shadow' : 'text-red-200/70'
              }`}
            >
              Sign up
            </button>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit} autoComplete="off">
            <AnimatePresence mode="wait">
              {isSignup && (
                <motion.div
                  key="signup-fields"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="space-y-4"
                >
                  <div className="grid gap-4 sm:grid-cols-2">
                    {renderInput({
                      label: 'First name',
                      name: 'first_name',
                      type: 'text',
                      placeholder: 'First name',
                      onChange: handleChange,
                      required: true,
                      value: form.first_name,
                      icon: <UserRound className="h-4 w-4" />
                    })}
                    {renderInput({
                      label: 'Last name',
                      name: 'last_name',
                      type: 'text',
                      placeholder: 'Last name',
                      onChange: handleChange,
                      required: true,
                      value: form.last_name,
                      icon: <UserRound className="h-4 w-4" />
                    })}
                  </div>
                  {renderInput({
                    label: 'Username',
                    name: 'username',
                    type: 'text',
                    placeholder: 'Preferred username',
                    onChange: handleChange,
                    required: true,
                    value: form.username,
                    icon: <Shield className="h-4 w-4" />,
                    helperText: (!usernameEdited && suggestedUsername && form.username === suggestedUsername)
                      ? 'Suggested available username'
                      : undefined
                  })}
                  {renderInput({
                    label: 'Email address',
                    name: 'email',
                    type: 'email',
                    placeholder: 'name@example.com',
                    onChange: handleChange,
                    required: true,
                    value: form.email,
                    icon: <Mail className="h-4 w-4" />
                  })}
                  {renderInput({
                    label: 'Mobile number',
                    name: 'phone_number',
                    type: 'tel',
                    placeholder: '+97798XXXXXXXX',
                    onChange: handleChange,
                    required: false,
                    value: form.phone_number,
                    icon: <Mail className="h-4 w-4" />
                  })}
                  <div className="space-y-2 text-sm text-slate-400">
                    <span className="font-medium text-slate-200">Mobile OTP Verification</span>
                    <div className="flex gap-2">
                      <div className="flex-1">
                        {renderInput({
                          label: 'OTP code',
                          name: 'otp',
                          type: 'text',
                          placeholder: '6-digit code',
                          onChange: handleChange,
                          required: true,
                          value: form.otp,
                          icon: <Shield className="h-4 w-4" />
                        })}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={handleRequestOtp}
                        disabled={otpLoading}
                        className="rounded-xl bg-red-700 px-3 py-2 text-xs font-semibold text-white transition hover:bg-red-600 disabled:opacity-60"
                      >
                        {otpLoading ? 'Please wait...' : otpSent ? 'Resend OTP' : 'Send OTP'}
                      </button>
                      <button
                        type="button"
                        onClick={handleVerifyOtp}
                        disabled={otpLoading || !otpSent}
                        className="rounded-xl bg-red-500 px-3 py-2 text-xs font-semibold text-white transition hover:bg-red-400 disabled:opacity-60"
                      >
                        Verify OTP
                      </button>
                    </div>
                    <p className={`text-xs ${otpVerified ? 'text-emerald-300' : 'text-red-200/70'}`}>
                      {otpVerified ? 'OTP verified. You can create account now.' : 'Verify mobile OTP before signup.'}
                    </p>
                  </div>
                  {renderDOB()}
                </motion.div>
              )}
            </AnimatePresence>

            {!isSignup && renderInput({
              label: 'Email or username',
              name: 'identifier',
              type: 'text',
              placeholder: 'name@example.com or username',
              onChange: handleChange,
              required: true,
              value: form.identifier,
              icon: <Mail className="h-4 w-4" />
            })}

            {renderInput({
              label: 'Password',
              name: 'password',
              type: showPassword ? 'text' : 'password',
              value: form.password,
              onChange: handleChange,
              required: true,
              placeholder: 'Enter password',
              icon: <Lock className="h-4 w-4" />,
              rightSlot: (
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="p-2 text-red-200/50 hover:text-red-100"
                  aria-label="Toggle password visibility"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              )
            })}

            {!isSignup && (
              <div className="space-y-3 rounded-2xl border border-red-900/40 bg-[#1a0b0e] p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-slate-200">Face Login</p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={startCamera}
                      className="rounded-lg bg-red-700 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-red-600"
                    >
                      Start camera
                    </button>
                    <button
                      type="button"
                      onClick={stopCamera}
                      className="rounded-lg border border-red-700/70 px-2.5 py-1.5 text-xs font-semibold text-red-200 hover:bg-red-900/30"
                    >
                      Stop
                    </button>
                  </div>
                </div>

                <div className="overflow-hidden rounded-xl border border-red-900/40 bg-black/50">
                  <video ref={videoRef} className="h-44 w-full object-cover" muted playsInline autoPlay />
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={captureFace}
                    disabled={!cameraActive}
                    className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-3 py-2 text-xs font-semibold text-white hover:bg-red-500 disabled:opacity-60"
                  >
                    <Camera className="h-4 w-4" />
                    Capture face
                  </button>
                  <span className="text-xs text-red-200/70">
                    {capturedFaceImage ? 'Face image captured' : 'Capture a clear front-facing image'}
                  </span>
                </div>

                {capturedFaceImage && (
                  <img src={capturedFaceImage} alt="Captured face" className="h-24 w-24 rounded-lg border border-red-900/50 object-cover" />
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={handleFaceSignin}
                    disabled={faceActionLoading}
                    className="rounded-xl bg-red-500 py-2 text-xs font-semibold text-white hover:bg-red-400 disabled:opacity-60"
                  >
                    {faceActionLoading ? 'Please wait...' : 'Sign in with face'}
                  </button>
                  <button
                    type="button"
                    onClick={handleSetupFaceLogin}
                    disabled={faceActionLoading}
                    className="rounded-xl border border-red-700/70 py-2 text-xs font-semibold text-red-100 hover:bg-red-900/20 disabled:opacity-60"
                  >
                    {faceActionLoading ? 'Please wait...' : 'Enable face login'}
                  </button>
                </div>
                <p className="text-xs text-red-200/55">
                  First time: enter password once and click Enable face login. After that, you can use Sign in with face.
                </p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-2xl bg-red-500 py-3 font-semibold text-white shadow-lg shadow-red-900/40 transition hover:bg-red-400 disabled:opacity-60"
            >
              {loading ? 'Processing…' : isSignup ? 'Create account' : 'Enter workspace'}
            </button>

            <p className="text-xs text-red-200/55">
              Credentials stay encrypted within the Devanagari Character Detection System.
            </p>
          </form>
        </div>
      </motion.div>
    </div>
  );
};

export default Auth;