import React from 'react';

interface LogoProps {
  size?: 'sm' | 'md';
  className?: string;
}

const Logo: React.FC<LogoProps> = ({ size = 'md', className = '' }) => {
  const box = size === 'sm' ? 'w-6 h-6 text-xs' : 'w-8 h-8 text-sm';
  const title = size === 'sm' ? 'text-base' : 'text-xl';
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className={`${box} rounded-lg bg-primary-600 flex items-center justify-center text-white font-bold`}>
        V
      </div>
      <span className={`${title} font-bold text-primary-600 tracking-tight`}>VERSUS</span>
      <span className="text-sm text-gray-500">| VCOO</span>
    </div>
  );
};

export default Logo;
