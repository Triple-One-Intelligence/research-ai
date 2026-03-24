import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import type { EntitySuggestion } from '../../types';
import { searchEntities } from '../../api';
import { IconOrganization, IconPerson } from '../RightPanel/RightPanelIcons';
import './EntitySearchBar.css';

interface EntitySearchBarProps {
  onSelect: (entity: EntitySuggestion) => void;
  onClear: () => void;
  selectedEntity: EntitySuggestion | null;
}

const EntitySearchBar = ({ onSelect, onClear, selectedEntity }: EntitySearchBarProps) => {
  const { t } = useTranslation();
  const [query, setQuery] = useState(selectedEntity?.label ?? '');
  const [suggestions, setSuggestions] = useState<EntitySuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLUListElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!selectedEntity) return;
    setQuery(selectedEntity.label);
    setSuggestions([]);
    setShowDropdown(false);
    setActiveIndex(-1);
  }, [selectedEntity]);

  const performSearch = useCallback(async (searchQuery: string) => {
    if (searchQuery.trim().length < 2) {
      setSuggestions([]);
      setShowDropdown(false);
      return;
    }

    setLoading(true);
    try {
      const results = await searchEntities(searchQuery);
      setSuggestions(results);
      setShowDropdown(results.length > 0);
    } catch (error) {
      console.error('Search failed:', error);
      setSuggestions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setQuery(value);
    setActiveIndex(-1);

    if (selectedEntity && value !== selectedEntity.label) {
      onClear();
    }

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(() => {
      performSearch(value);
    }, 300);
  };

  const handleSelect = (entity: EntitySuggestion) => {
    setQuery(entity.label);
    setSuggestions([]);
    setShowDropdown(false);
    setActiveIndex(-1);
    onSelect(entity);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showDropdown || suggestions.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : prev));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case 'Enter':
        e.preventDefault();
        if (activeIndex >= 0 && activeIndex < suggestions.length) {
          handleSelect(suggestions[activeIndex]);
        }
        break;
      case 'Escape':
        setShowDropdown(false);
        setActiveIndex(-1);
        break;
      default:
        break;
    }
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        inputRef.current &&
        !inputRef.current.contains(event.target as Node) &&
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setShowDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (activeIndex >= 0 && dropdownRef.current) {
      const activeElement = dropdownRef.current.children[activeIndex] as HTMLElement;
      if (activeElement) {
        activeElement.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [activeIndex]);

  const renderEntityIcon = (type: EntitySuggestion['type']) =>
    type === 'person' ? <IconPerson className="entity-type-icon" /> : <IconOrganization className="entity-type-icon" />;

  return (
    <div className="entity-search-bar">
      <label className="search-label" htmlFor="entity-search">
        {t('leftPanel.searchLabel')}
      </label>

      <div className="search-input-container">
        <input
          ref={inputRef}
          id="entity-search"
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (suggestions.length > 0) setShowDropdown(true);
          }}
          placeholder={t('leftPanel.searchPlaceholder')}
          className={`search-input ${selectedEntity ? 'has-selection' : ''}`}
          role="combobox"
          aria-expanded={showDropdown}
          aria-haspopup="listbox"
          aria-controls="search-suggestions"
          aria-activedescendant={activeIndex >= 0 ? `suggestion-${activeIndex}` : undefined}
          autoComplete="off"
        />
        <div className="search-input-actions" aria-hidden="true">
          {loading && <span className="search-spinner" aria-label={t('leftPanel.loading')} />}
          {selectedEntity && (
            <div className="selected-inline">
              <span className={`entity-type-badge inline ${selectedEntity.type}`}>
                {renderEntityIcon(selectedEntity.type)}
              </span>
              <button
                className="clear-entity-btn inline"
                onClick={() => {
                  onClear();
                  setQuery('');
                  setSuggestions([]);
                  setShowDropdown(false);
                  setActiveIndex(-1);
                  inputRef.current?.focus();
                }}
                aria-label={t('leftPanel.clearSelection')}
              >
                x
              </button>
            </div>
          )}
        </div>
      </div>

      {showDropdown && suggestions.length > 0 && (
        <ul
          ref={dropdownRef}
          id="search-suggestions"
          className="suggestions-dropdown"
          role="listbox"
          aria-label={t('leftPanel.searchSuggestions')}
        >
          {suggestions.map((suggestion, index) => (
            <li
              key={suggestion.id}
              id={`suggestion-${index}`}
              role="option"
              aria-selected={index === activeIndex}
              className={`suggestion-item ${index === activeIndex ? 'active' : ''}`}
              onClick={() => handleSelect(suggestion)}
              onMouseEnter={() => setActiveIndex(index)}
            >
              <span className={`entity-type-badge ${suggestion.type}`}>
                {renderEntityIcon(suggestion.type)}
              </span>
              <div className="suggestion-content">
                <span className="suggestion-label">{suggestion.label}</span>
                {suggestion.extra && (
                  <span className="suggestion-extra">{suggestion.extra}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {showDropdown && query.length >= 2 && suggestions.length === 0 && !loading && (
        <div className="no-results">{t('leftPanel.noResults')}</div>
      )}
    </div>
  );
};

export default EntitySearchBar;
