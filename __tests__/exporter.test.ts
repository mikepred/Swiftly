import { describe, it, expect } from 'vitest'
import { formatCsvField } from '@/lib/exporter'

describe('formatCsvField - CSV Formula Injection Prevention', () => {
  it('should preserve standard safe text without formula triggers', () => {
    expect(formatCsvField('Hello world')).toBe('"Hello world"')
    expect(formatCsvField('12345')).toBe('"12345"')
    expect(formatCsvField('user@example.com')).toBe('"user@example.com"')
  })

  it('should escape double quotes correctly', () => {
    expect(formatCsvField('Hello "World"')).toBe('"Hello ""World"""')
  })

  it('should prepend single quote to fields starting with equals sign (=)', () => {
    expect(formatCsvField('=1+1')).toBe('"\'=1+1"')
    expect(formatCsvField("=CMD|' /C calc'!A1")).toBe('"\'=CMD|\' /C calc\'!A1"')
  })

  it('should prepend single quote to fields starting with plus (+)', () => {
    expect(formatCsvField('+1+1')).toBe('"\'\+1+1"')
  })

  it('should prepend single quote to fields starting with minus (-)', () => {
    expect(formatCsvField('-1+1')).toBe('"\'\-1+1"')
  })

  it('should prepend single quote to fields starting with at sign (@)', () => {
    expect(formatCsvField('@SUM(A1:A10)')).toBe('"\'@SUM(A1:A10)"')
  })

  it('should handle leading whitespace before formula characters', () => {
    expect(formatCsvField('   =1+1')).toBe('"\'   =1+1"')
    expect(formatCsvField('\t=1+1')).toBe('"\'\t=1+1"')
  })
})
