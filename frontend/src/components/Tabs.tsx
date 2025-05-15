import React, { useState, ReactNode } from 'react';

interface TabsProps {
  defaultValue: string;
  children: ReactNode;
}

interface TabsHeaderProps {
  children: ReactNode;
}

interface TabItemProps {
  value: string;
  onClick?: () => void;
  children: ReactNode;
}

interface TabsBodyProps {
  children: ReactNode;
}

export const Tabs: React.FC<TabsProps> = ({ defaultValue, children }) => {
  const [activeTab, setActiveTab] = useState<string>(defaultValue);

  // Клонируем дочерние элементы и передаем им activeTab
  const childrenWithProps = React.Children.map(children, child => {
    if (React.isValidElement(child)) {
      return React.cloneElement(child, { activeTab, setActiveTab });
    }
    return child;
  });

  return (
    <div className="tabs-container">
      {childrenWithProps}
    </div>
  );
};

export const TabsHeader: React.FC<TabsHeaderProps> = ({ children, activeTab, setActiveTab }) => {
  // Клонируем дочерние элементы (TabItem) и передаем им activeTab и setActiveTab
  const childrenWithProps = React.Children.map(children, child => {
    if (React.isValidElement(child)) {
      return React.cloneElement(child, { activeTab, setActiveTab });
    }
    return child;
  });

  return (
    <div className="tabs-header flex border-b border-gray-200 dark:border-gray-700">
      {childrenWithProps}
    </div>
  );
};

export const TabItem: React.FC<TabItemProps> = ({ value, onClick, children, activeTab, setActiveTab }) => {
  const isActive = activeTab === value;
  
  const handleClick = () => {
    setActiveTab(value);
    if (onClick) onClick();
  };

  return (
    <button
      className={`px-4 py-2 font-medium text-sm ${
        isActive 
          ? 'text-blue-600 border-b-2 border-blue-600 dark:text-blue-500 dark:border-blue-500' 
          : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
      }`}
      onClick={handleClick}
    >
      {children}
    </button>
  );
};

export const TabsBody: React.FC<TabsBodyProps> = ({ children }) => {
  return (
    <div className="tabs-body pt-4">
      {children}
    </div>
  );
};

export default Tabs; 