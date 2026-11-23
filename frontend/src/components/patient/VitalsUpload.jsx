import React, { useState, useEffect, useRef } from 'react';
import { 
  Upload, FileText, CheckCircle2, ArrowRight, AlertTriangle, 
  Sparkles, X, Check, Trash2, Plus, Camera, Loader2 
} from 'lucide-react';
import { submitVitals, uploadReportFile, fetchSessionReports, deleteReportFile } from '../../services/api';

export default function VitalsUpload({ patient, session, onVitalsCompleted }) {
  const [height, setHeight] = useState('170');
  const [weight, setWeight] = useState('68');
  const [ayushSystem] = useState('allopathy');
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  
  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);

  // Load any previously uploaded reports for this session
  useEffect(() => {
    let isMounted = true;
    if (patient?.patient_token && session?.session_id) {
      fetchSessionReports(patient.patient_token, session.session_id)
        .then((existing) => {
          if (isMounted && Array.isArray(existing) && existing.length > 0) {
            setReports(existing);
          }
        })
        .catch((e) => console.warn('Could not load existing session reports:', e));
    }
    return () => { isMounted = false; };
  }, [patient?.patient_token, session?.session_id]);

  // Live BMI calculation
  const hNum = parseFloat(height);
  const wNum = parseFloat(weight);
  const bmi = (hNum > 0 && wNum > 0) ? (wNum / Math.pow(hNum / 100, 2)).toFixed(1) : '—';
  
  let bmiCategory = '—';
  let bmiColor = 'text-slate-600';
  if (bmi !== '—') {
    const b = parseFloat(bmi);
    if (b < 18.5) { bmiCategory = 'Underweight'; bmiColor = 'text-blue-600'; }
    else if (b <= 22.9) { bmiCategory = 'Normal'; bmiColor = 'text-emerald-700'; }
    else if (b <= 24.9) { bmiCategory = 'Overweight'; bmiColor = 'text-amber-700'; }
    else { bmiCategory = 'Obese'; bmiColor = 'text-red-700'; }
  }

  // Unified file processor for both multi-selection, single-file, and drag-and-drop
  const handleFiles = async (filesList) => {
    if (!filesList || filesList.length === 0) return;
    const filesToUpload = Array.from(filesList);

    // Immediately reset DOM input values so re-selecting the same file always triggers
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (cameraInputRef.current) cameraInputRef.current.value = '';

    setUploading(true);
    setError(null);

    const total = filesToUpload.length;
    let successCount = 0;
    const failedFiles = [];

    // Process files sequentially so each one gets individual progress & immediate UI display
    for (let i = 0; i < total; i++) {
      const file = filesToUpload[i];
      setUploadStatus(`Uploading & reading ${i + 1} of ${total}: ${file.name}...`);

      try {
        const data = await uploadReportFile(patient.patient_token, session.session_id, file);
        setReports((prev) => {
          // Avoid duplicate report entries
          if (prev.some((r) => r.report_id === data.report_id)) return prev;
          return [...prev, data];
        });
        successCount++;
      } catch (err) {
        console.error(`Failed to process ${file.name}:`, err);
        failedFiles.push(file.name);
      }
    }

    if (failedFiles.length > 0) {
      if (successCount > 0) {
        setError(`Uploaded ${successCount} document(s). Could not process: ${failedFiles.join(', ')}.`);
      } else {
        setError('Failed to process the selected file(s). You can proceed without reports or try another file.');
      }
    }

    setUploading(false);
    setUploadStatus('');
  };

  const handleInputChange = (e) => {
    handleFiles(e.target.files);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleRemoveReport = async (indexToRemove, reportId) => {
    setReports((prev) => prev.filter((_, idx) => idx !== indexToRemove));
    if (reportId && patient?.patient_token && session?.session_id) {
      try {
        await deleteReportFile(patient.patient_token, session.session_id, reportId);
      } catch (e) {
        console.warn('Backend delete report error:', e);
      }
    }
  };

  const handleSaveAndContinue = async () => {
    if (!height || !weight || parseFloat(height) <= 30 || parseFloat(weight) <= 1) {
      setError('Please provide valid height and weight');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const vData = await submitVitals(
        patient.patient_token,
        height,
        weight,
        ayushSystem,
        session?.session_id
      );
      onVitalsCompleted({
        height_cm: vData.height_cm,
        weight_kg: vData.weight_kg,
        bmi: vData.bmi,
        bmi_category: vData.bmi_category,
        ayush_system: ayushSystem,
        reports
      });
    } catch (err) {
      console.error('Vitals submission error:', err);
      setError(err?.message || 'Failed to record vitals. Please check connection.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div className="text-center space-y-1">
        <h2 className="text-2xl font-bold text-slate-800">Vitals & Optional Reports</h2>
        <p className="text-xs text-slate-500">
          Enter your basic measurements. Diagnostic reports are completely optional.
        </p>
      </div>

      {/* Height & Weight Inputs with Code-Computed BMI */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-800">Physical Measurements</h3>
          <span className="px-2.5 py-1 bg-amber-100 text-amber-900 text-[11px] font-semibold rounded-full uppercase">
            Self-Reported
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Height / कद (cm)
            </label>
            <input
              type="number"
              value={height}
              onChange={(e) => setHeight(e.target.value)}
              placeholder="e.g. 170"
              className="w-full px-3 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-emerald-600 focus:outline-none text-base"
              min="50"
              max="250"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">
              Weight / वजन (kg)
            </label>
            <input
              type="number"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              placeholder="e.g. 68"
              className="w-full px-3 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-emerald-600 focus:outline-none text-base"
              min="10"
              max="250"
            />
          </div>
        </div>

        {/* Real-time Computed BMI Display */}
        <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 flex items-center justify-between">
          <div>
            <p className="text-xs text-slate-500">Computed Body Mass Index (BMI):</p>
            <p className="text-lg font-bold text-slate-800">
              {bmi} <span className="text-xs font-normal text-slate-500">kg/m²</span>
            </p>
          </div>
          <div className="text-right">
            <span className={`text-sm font-bold ${bmiColor}`}>
              {bmiCategory}
            </span>
            <p className="text-[10px] text-slate-400">Formula: weight / (height_m)²</p>
          </div>
        </div>
      </div>

      {/* Diagnostic Report Upload (Explicitly Optional) */}
      <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-base font-semibold text-slate-800">Upload Reports or Prescriptions</h3>
              <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-bold rounded uppercase">
                Optional
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Select one or multiple files at once. You can also take photos directly from your phone.
            </p>
          </div>
        </div>

        {/* Hidden File Inputs */}
        {/* 1. Multi-file gallery/document picker */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,application/pdf"
          onChange={handleInputChange}
          style={{ display: 'none' }}
        />
        {/* 2. Direct Camera trigger for mobile prescription capture */}
        <input
          ref={cameraInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleInputChange}
          style={{ display: 'none' }}
        />

        {/* Upload Dropzone & Action Buttons */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-5 flex flex-col items-center justify-center transition w-full min-h-[120px] ${
            isDragging 
              ? 'border-emerald-600 bg-emerald-50/60 scale-[1.01]' 
              : 'border-slate-300 bg-slate-50 hover:bg-emerald-50/40 hover:border-emerald-600'
          }`}
        >
          {uploading ? (
            <div className="flex flex-col items-center justify-center space-y-2 py-2">
              <Loader2 className="w-8 h-8 text-emerald-700 animate-spin" />
              <p className="text-sm font-semibold text-emerald-800">
                {uploadStatus || 'Processing documents...'}
              </p>
              <p className="text-xs text-slate-500">Transcribing lab values without interpreting results</p>
            </div>
          ) : (
            <>
              <Upload className="w-8 h-8 text-emerald-700 mb-2" />
              <p className="text-sm font-semibold text-slate-800 text-center">
                {reports.length > 0 ? '+ Add More Reports or Prescriptions' : 'Choose Files to Upload'}
              </p>
              <p className="text-xs text-slate-400 mt-0.5 text-center">
                Drag & drop multiple files here, or choose an option below
              </p>

              {/* Action Buttons: Choose Multiple Files vs Camera */}
              <div className="flex flex-wrap items-center justify-center gap-3 mt-4">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-lg text-xs font-semibold shadow-sm flex items-center space-x-1.5 transition"
                >
                  <Plus className="w-4 h-4" />
                  <span>Select Files / Photos</span>
                </button>
                <button
                  type="button"
                  onClick={() => cameraInputRef.current?.click()}
                  className="px-4 py-2 bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold shadow-sm flex items-center space-x-1.5 transition"
                >
                  <Camera className="w-4 h-4 text-emerald-700" />
                  <span>Take Photo (Camera)</span>
                </button>
              </div>
            </>
          )}
        </div>

        {/* Extracted Reports Display */}
        {reports.length > 0 && (
          <div className="space-y-3 pt-2">
            <div className="flex items-center justify-between">
              <p className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                Attached Reports ({reports.length}):
              </p>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="text-xs text-emerald-700 font-bold hover:underline flex items-center space-x-1 disabled:opacity-50"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add another</span>
              </button>
            </div>

            {reports.map((rep, idx) => (
              <div key={rep.report_id || idx} className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-2 text-xs">
                <div className="flex items-center justify-between font-medium text-slate-800">
                  <span className="flex items-center space-x-2 truncate">
                    <FileText className="w-4 h-4 text-emerald-700 flex-shrink-0" />
                    <span className="truncate font-semibold">{rep.file_name}</span>
                  </span>
                  <div className="flex items-center space-x-2 flex-shrink-0">
                    <span className="text-emerald-700 flex items-center space-x-1 text-[11px] bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-medium">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Transcribed</span>
                    </span>
                    <button
                      type="button"
                      onClick={() => handleRemoveReport(idx, rep.report_id)}
                      title="Remove this report"
                      className="p-1 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded transition"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Extracted lab values if present */}
                {rep.lab_values?.length > 0 && (
                  <div className="pl-6 space-y-1 border-l-2 border-emerald-300 ml-1 mt-1">
                    {rep.lab_values.map((lv, lIdx) => (
                      <p key={lIdx} className="text-slate-600">
                        • <span className="font-medium text-slate-800">{lv.test_name}:</span> {lv.raw_value}
                      </p>
                    ))}
                  </div>
                )}

                {/* Extracted candidate medicines if present */}
                {rep.candidate_medicines?.length > 0 && (
                  <div className="pl-6 space-y-1 border-l-2 border-amber-300 ml-1 mt-1">
                    <p className="text-[11px] font-semibold text-slate-700">Detected Medicines:</p>
                    {rep.candidate_medicines.map((m, mIdx) => (
                      <p key={mIdx} className="text-slate-600">
                        • {m.name} {m.strength ? `(${m.strength})` : ''}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-600 font-medium bg-red-50 p-2.5 rounded-lg border border-red-200">
          {error}
        </p>
      )}

      {/* Primary Action Button */}
      <button
        onClick={handleSaveAndContinue}
        disabled={loading || uploading}
        className="w-full bg-emerald-700 hover:bg-emerald-800 text-white font-semibold py-3.5 rounded-lg shadow transition flex items-center justify-center space-x-2 min-h-touch text-base disabled:opacity-60"
      >
        {loading ? (
          <span>Saving Vitals...</span>
        ) : (
          <>
            <span>
              {reports.length > 0 
                ? `Proceed to Voice Interview (${reports.length} report${reports.length > 1 ? 's' : ''} attached)` 
                : 'Proceed to Voice Interview (Without Reports)'}
            </span>
            <ArrowRight className="w-5 h-5" />
          </>
        )}
      </button>
    </div>
  );
}
