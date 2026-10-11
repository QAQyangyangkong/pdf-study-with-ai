import { createContext } from 'react';
import type { Page } from '../types';

export const NavigationContext = createContext<(page: Page) => void>(() => undefined);
