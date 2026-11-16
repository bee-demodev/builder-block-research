import './styles/tokens.css';
import './styles/app.css';
import './styles/tcm.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';

/*
 * Charts: TradingView Lightweight Charts, Apache License 2.0.
 * Attribution notice from its NOTICE file:
 *   TradingView Lightweight Charts™
 *   Copyright (с) 2025 TradingView, Inc. https://www.tradingview.com/
 */

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
