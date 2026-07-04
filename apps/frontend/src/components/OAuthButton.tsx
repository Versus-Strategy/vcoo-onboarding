import React from 'react';

interface OAuthButtonProps {
  proveedor: string;
  onConnect: () => Promise<void>;
  loading?: boolean;
}

const OAuthButton: React.FC<OAuthButtonProps> = ({ proveedor, onConnect, loading }) => {
  return (
    <button
      onClick={onConnect}
      disabled={loading}
      className="w-full flex items-center justify-center px-4 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
    >
      {loading ? (
        <svg className="animate-spin h-5 w-5 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      ) : (
        <span className="text-sm font-medium text-gray-700">Conectar con {proveedor}</span>
      )}
    </button>
  );
};

export default OAuthButton;
