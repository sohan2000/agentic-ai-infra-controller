import React from 'react'
import { Card } from '@mui/material'


const ChartsPanel = () => {
  return (
    <div>
      <Card variant='outlined'
        sx={{
          backgroundColor: 'var(--color-card)',
          color: 'var(--color-text-primary)',
          padding: "1em",
        }}
      >Chat Panel</Card>
    </div>
  )
}

export default ChartsPanel