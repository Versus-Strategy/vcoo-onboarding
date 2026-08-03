import React from 'react';
import { ExclamationTriangleIcon, CheckIcon } from '@heroicons/react/24/outline';

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

  const isDegraded = (idx: number) =>
    pasosDegradados.includes(idx);

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

      <div className="flex justify-between overflow-x-auto gap-1 pb-1">
        {pasos.map((paso, idx) => {
          const isCurrent = idx === pasoActual;
          const isUnlocked = idx <= unlockedLimit;
          const degraded = isDegraded(idx);
          const isNext = idx === unlockedLimit + 1;
          const isDone = idx < pasoCompletado;
          const showCheckmark = !isCurrent && (isDone || degraded) && !isNext;
          return (
          <div key={idx}
            onClick={() => isUnlocked && onStepClick?.(idx)}
            className={`flex flex-col items-center flex-shrink-0 min-w-[56px] text-center ${isUnlocked && onStepClick ? 'cursor-pointer' : ''}`}
          >
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                isCurrent && !degraded ? 'bg-primary-100 text-primary-600 border-2 border-primary-600 ring-4 ring-primary-200'
                : isCurrent && degraded ? 'bg-yellow-100 text-yellow-600 border-2 border-yellow-600 ring-4 ring-yellow-200'
                : degraded ? 'bg-yellow-100 text-yellow-600 border-2 border-yellow-400'
                : showCheckmark ? 'bg-primary-100 text-primary-600 border-2 border-primary-400'
                : isNext ? 'bg-gray-100 text-gray-400 border-2 border-dashed border-gray-300'
                : 'bg-gray-100 text-gray-400 border-2 border-gray-200'
              }`}
            >
              {degraded && !isCurrent ? (
                <ExclamationTriangleIcon className="w-4 h-4" />
              ) : showCheckmark ? (
                <CheckIcon className="w-4 h-4" />
              ) : (
                idx + 1
              )}
            </div>
            <span
              className={`mt-1 text-xs ${
                isCurrent || showCheckmark || degraded
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
