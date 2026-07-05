import React from 'react';

interface StepIndicatorProps {
  pasoActual: number;
  pasoCompletado: number;
  pasosTotales: number;
  pasos: string[];
  onStepClick?: (idx: number) => void;
  maxUnlocked?: number;
  pasosDegradados?: number[];
  progreso?: number;
}

const StepIndicator: React.FC<StepIndicatorProps> = ({
  pasoActual, pasoCompletado, pasosTotales, pasos,
  onStepClick, maxUnlocked, pasosDegradados = [], progreso,
}) => {
  const unlockedLimit = maxUnlocked ?? pasoCompletado;
  const pasosReales = pasosTotales - 1;
  const porcentaje = progreso ?? Math.round(Math.min(pasoCompletado, pasosReales) / pasosReales * 100);

  const status = (idx: number): 'done' | 'degraded' | 'current' | 'next' | 'locked' => {
    if (pasosDegradados.includes(idx)) return 'degraded';
    if (idx === pasoActual) return 'current';
    if (pasosDegradados.length > 0 && idx === pasosTotales - 1) return 'degraded';
    if (idx < pasoCompletado) return 'done';
    if (idx <= unlockedLimit) return 'done';
    if (idx === unlockedLimit + 1) return 'next';
    return 'locked';
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold text-gray-900">Progreso de Configuración</h2>
        <span className="text-sm text-gray-500">{porcentaje}% completo</span>
      </div>

      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className="bg-primary-600 h-2 rounded-full transition-all duration-500"
          style={{ width: `${porcentaje}%` }}
        />
      </div>

      <div className="flex justify-between">
        {pasos.map((paso, idx) => {
          const st = status(idx);
          const unlocked = st !== 'locked';
          return (
          <div key={idx}
            onClick={() => unlocked && onStepClick?.(idx)}
            className={`flex flex-col items-center ${unlocked && onStepClick ? 'cursor-pointer' : ''}`}
          >
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                st === 'done' ? 'bg-primary-600 text-white'
                : st === 'degraded' ? 'bg-yellow-100 text-yellow-600 border-2 border-yellow-400'
                : st === 'current' ? 'bg-primary-600 text-white ring-4 ring-primary-200'
                : st === 'next' ? 'bg-gray-100 text-gray-600 border-2 border-dashed border-gray-300'
                : 'bg-gray-200 text-gray-500'
              }`}
            >
              {st === 'done' ? (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                idx + 1
              )}
            </div>
            <span
              className={`mt-1 text-xs ${
                st === 'done' || st === 'current' || st === 'degraded'
                  ? 'text-primary-600 font-medium'
                  : 'text-gray-400'
              }`}
            >
              {paso}
            </span>
          </div>
          );
        })}
      </div>
    </div>
  );
};

export default StepIndicator;
