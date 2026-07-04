import React from 'react';

interface StepIndicatorProps {
  pasoActual: number;
  pasosTotales: number;
  pasos: string[];
}

const StepIndicator: React.FC<StepIndicatorProps> = ({ pasoActual, pasosTotales, pasos }) => {
  const porcentaje = Math.round((pasoActual / pasosTotales) * 100);

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
        {pasos.map((paso, idx) => (
          <div key={idx} className="flex flex-col items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                idx < pasoActual
                  ? 'bg-primary-600 text-white'
                  : idx === pasoActual
                  ? 'bg-primary-100 text-primary-600 border-2 border-primary-600'
                  : 'bg-gray-200 text-gray-500'
              }`}
            >
              {idx < pasoActual ? '✓' : idx + 1}
            </div>
            <span
              className={`mt-1 text-xs ${
                idx <= pasoActual ? 'text-primary-600 font-medium' : 'text-gray-400'
              }`}
            >
              {paso}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default StepIndicator;
