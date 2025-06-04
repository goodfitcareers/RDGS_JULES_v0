import React, { useState, useEffect, useMemo } from 'react';
import { RoleRead, RoleStatus } from '../types';

// Simple fallback tokenizer (counts words and punctuation)
const estimateTokens = (text: string): number => {
  if (!text) return 0;
  // Matches words and common punctuation as separate tokens
  const tokens = text.match(/[\w'-]+|[.,!?;:]/g);
  return tokens ? tokens.length : 0;
};

// PII Patterns (examples)
const PII_PATTERNS: { name: string; regex: RegExp }[] = [
  { name: 'Email', regex: /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g },
  { name: 'SSN (Example)', regex: /\b\d{3}-\d{2}-\d{4}\b/g },
  // Add more patterns from sensitive_patterns.py as needed
  { name: 'Phone (US Example)', regex: /\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b/g }
];

const MAX_TOKENS = 8096;
const WARNING_TOKENS = 7500;

interface RoleEditorProps {
  role: Pick<RoleRead, 'id' | 'input_text_compact' | 'revision' | 'status'>; // Only relevant parts of the role
  onSave: (updatedData: { input_text_compact: string; revision: number; newStatus: RoleStatus }) => Promise<void>;
  onCancel: () => void; // To close or hide the editor
  isSaving: boolean; // To disable button during save
}

const RoleEditor: React.FC<RoleEditorProps> = ({ role, onSave, onCancel, isSaving }) => {
  const [currentInputText, setCurrentInputText] = useState<string>(role.input_text_compact || '');
  const [tokenCount, setTokenCount] = useState<number>(0);
  const [piiWarnings, setPiiWarnings] = useState<string[]>([]);

  useEffect(() => {
    setCurrentInputText(role.input_text_compact || '');
  }, [role.input_text_compact]);

  useEffect(() => {
    // Debounce token counting and PII check slightly for better performance
    const handler = setTimeout(() => {
      const count = estimateTokens(currentInputText);
      setTokenCount(count);

      const warnings: string[] = [];
      PII_PATTERNS.forEach(pattern => {
        // Reset regex state for global flags
        pattern.regex.lastIndex = 0;
        if (pattern.regex.test(currentInputText)) {
          warnings.push(`Potential ${pattern.name} detected.`);
        }
      });
      setPiiWarnings(warnings);
    }, 300); // 300ms debounce

    return () => clearTimeout(handler);
  }, [currentInputText]);

  const handleSave = () => {
    if (tokenCount > MAX_TOKENS) {
      // This should ideally be prevented by disabling the button
      alert("Cannot save: token count exceeds maximum limit.");
      return;
    }
    onSave({
      input_text_compact: currentInputText,
      revision: role.revision,
      newStatus: RoleStatus.InputCurated, // Set status to InputCurated upon saving curated text
    });
  };

  const tokenCountColor = useMemo(() => {
    if (tokenCount > MAX_TOKENS) return 'text-red-600 font-bold';
    if (tokenCount > WARNING_TOKENS) return 'text-yellow-600 font-semibold';
    return 'text-gray-600';
  }, [tokenCount]);

  const isSaveDisabled = tokenCount > MAX_TOKENS || isSaving;

  return (
    <div className="p-4 bg-gray-50 rounded-lg shadow space-y-4">
      <h3 className="text-lg font-semibold text-gray-800">Curate Input Text (HITL 2)</h3>
      <p className="text-sm text-gray-600">
        Edit the compact input text below. This text will be used for further processing or analysis.
        Original Status: <span className="font-medium">{role.status}</span>
      </p>

      <textarea
        value={currentInputText}
        onChange={(e) => setCurrentInputText(e.target.value)}
        className="w-full h-60 p-3 border border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm whitespace-pre-wrap"
        placeholder="Enter or edit the compact input text for this role..."
      />

      <div className="flex justify-between items-center">
        <div className={`text-sm ${tokenCountColor}`}>
          Token Count: {tokenCount} / {MAX_TOKENS}
          {tokenCount > WARNING_TOKENS && tokenCount <= MAX_TOKENS && (
            <span className="ml-2 text-yellow-700">(Approaching limit)</span>
          )}
           {tokenCount > MAX_TOKENS && (
            <span className="ml-2 text-red-700">(Exceeded limit!)</span>
          )}
        </div>
      </div>

      {piiWarnings.length > 0 && (
        <div className="p-3 bg-yellow-50 border border-yellow-300 rounded-md">
          <h4 className="text-sm font-semibold text-yellow-800 mb-1">Potential PII Detected:</h4>
          <ul className="list-disc list-inside text-xs text-yellow-700">
            {piiWarnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex justify-end space-x-3 mt-4">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSaving}
          className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 rounded-md shadow-sm disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={isSaveDisabled}
          className="px-4 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-md shadow-sm disabled:bg-green-300"
        >
          {isSaving ? 'Saving...' : 'Save Curation'}
        </button>
      </div>
    </div>
  );
};

export default RoleEditor;
