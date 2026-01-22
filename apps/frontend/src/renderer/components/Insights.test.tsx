/**
 * @vitest-environment jsdom
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MessageBubble } from './Insights';
import type { InsightsChatMessage } from '../../shared/types';

describe('MessageBubble Truncation', () => {
  const mockMarkdownComponents = {};
  const mockOnCreateTask = () => {};

  it('renders short content without truncation UI', () => {
    const shortMessage: InsightsChatMessage = {
      id: 'test-1',
      role: 'user',
      content: 'Short message under 500 chars and 10 lines',
      timestamp: new Date()
    };

    render(
      <MessageBubble
        message={shortMessage}
        markdownComponents={mockMarkdownComponents}
        onCreateTask={mockOnCreateTask}
        isCreatingTask={false}
        taskCreated={false}
      />
    );

    // Should NOT show "Show more" button
    expect(screen.queryByText(/Show more/i)).not.toBeInTheDocument();
  });

  it('renders long content (>500 chars) with truncation and Show more button', () => {
    const longMessage: InsightsChatMessage = {
      id: 'test-2',
      role: 'user',
      content: 'a'.repeat(501), // 501 characters
      timestamp: new Date()
    };

    render(
      <MessageBubble
        message={longMessage}
        markdownComponents={mockMarkdownComponents}
        onCreateTask={mockOnCreateTask}
        isCreatingTask={false}
        taskCreated={false}
      />
    );

    // Should show "Show more ▼" button
    expect(screen.getByText(/Show more/i)).toBeInTheDocument();
    expect(screen.getByText(/▼/)).toBeInTheDocument();
  });

  it('renders content with >10 lines with truncation', () => {
    const manyLinesMessage: InsightsChatMessage = {
      id: 'test-3',
      role: 'user',
      content: Array(12).fill('Line').join('\n'), // 12 lines, <500 chars
      timestamp: new Date()
    };

    render(
      <MessageBubble
        message={manyLinesMessage}
        markdownComponents={mockMarkdownComponents}
        onCreateTask={mockOnCreateTask}
        isCreatingTask={false}
        taskCreated={false}
      />
    );

    // Should show "Show more ▼" button
    expect(screen.getByText(/Show more/i)).toBeInTheDocument();
  });

  it('expands content when Show more is clicked and changes button to Show less', () => {
    const longMessage: InsightsChatMessage = {
      id: 'test-4',
      role: 'user',
      content: 'a'.repeat(501),
      timestamp: new Date()
    };

    render(
      <MessageBubble
        message={longMessage}
        markdownComponents={mockMarkdownComponents}
        onCreateTask={mockOnCreateTask}
        isCreatingTask={false}
        taskCreated={false}
      />
    );

    const button = screen.getByRole('button', { name: /Show more/i });

    // Click to expand
    fireEvent.click(button);

    // Button should now say "Show less ▲"
    expect(screen.getByText(/Show less/i)).toBeInTheDocument();
    expect(screen.getByText(/▲/)).toBeInTheDocument();
  });

  it('collapses content when Show less is clicked', () => {
    const longMessage: InsightsChatMessage = {
      id: 'test-5',
      role: 'user',
      content: 'a'.repeat(501),
      timestamp: new Date()
    };

    render(
      <MessageBubble
        message={longMessage}
        markdownComponents={mockMarkdownComponents}
        onCreateTask={mockOnCreateTask}
        isCreatingTask={false}
        taskCreated={false}
      />
    );

    const button = screen.getByRole('button', { name: /Show more/i });

    // Expand
    fireEvent.click(button);
    expect(screen.getByText(/Show less/i)).toBeInTheDocument();

    // Collapse
    fireEvent.click(button);
    expect(screen.getByText(/Show more/i)).toBeInTheDocument();
  });

  it('does NOT truncate assistant messages', () => {
    const longAssistantMessage: InsightsChatMessage = {
      id: 'test-6',
      role: 'assistant',
      content: 'a'.repeat(501), // >500 chars but from assistant
      timestamp: new Date()
    };

    render(
      <MessageBubble
        message={longAssistantMessage}
        markdownComponents={mockMarkdownComponents}
        onCreateTask={mockOnCreateTask}
        isCreatingTask={false}
        taskCreated={false}
      />
    );

    // Should NOT show truncation UI for assistant messages
    expect(screen.queryByText(/Show more/i)).not.toBeInTheDocument();
  });
});
