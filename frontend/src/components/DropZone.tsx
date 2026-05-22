import React, { useCallback, useState } from "react";

interface Props {
  label: string;
  accept?: string;
  multiple?: boolean;
  files: File[];
  onChange: (files: File[]) => void;
}

export default function DropZone({ label, accept = ".dwg", multiple = false, files, onChange }: Props) {
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const dropped = Array.from(e.dataTransfer.files).filter((f) =>
        accept.split(",").some((ext) => f.name.toLowerCase().endsWith(ext.trim()))
      );
      if (!dropped.length) return;
      onChange(multiple ? [...files, ...dropped] : [dropped[0]]);
    },
    [files, multiple, accept, onChange]
  );

  const handleInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = Array.from(e.target.files ?? []);
      onChange(multiple ? [...files, ...selected] : [selected[0]]);
      e.target.value = "";
    },
    [files, multiple, onChange]
  );

  const removeFile = (idx: number) => {
    onChange(files.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-300">{label}</label>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 transition-colors cursor-pointer
          ${dragging ? "border-blue-400 bg-blue-950/30" : "border-gray-600 hover:border-gray-400 bg-gray-800/50"}`}
      >
        <input
          type="file"
          accept={accept}
          multiple={multiple}
          onChange={handleInput}
          className="absolute inset-0 opacity-0 cursor-pointer"
        />
        <svg className="h-8 w-8 text-gray-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        <p className="text-sm text-gray-400">
          {files.length === 0
            ? `드래그 앤 드롭 또는 클릭하여 선택`
            : multiple
            ? `${files.length}개 파일 선택됨 (추가 가능)`
            : files[0].name}
        </p>
        {accept && <p className="text-xs text-gray-500 mt-1">{accept} 파일</p>}
      </div>

      {/* 선택된 파일 목록 (multiple 모드) */}
      {multiple && files.length > 0 && (
        <ul className="max-h-36 overflow-y-auto space-y-1 rounded-md bg-gray-800 p-2">
          {files.map((f, idx) => (
            <li key={idx} className="flex items-center justify-between text-xs text-gray-300">
              <span className="truncate max-w-[calc(100%-2rem)]">{f.name}</span>
              <button
                type="button"
                onClick={() => removeFile(idx)}
                className="ml-2 flex-shrink-0 text-gray-500 hover:text-red-400"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
