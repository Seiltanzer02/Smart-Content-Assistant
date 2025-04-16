import React, { useState, useEffect } from 'react';
import { Box, Text, Grid, GridItem, Flex, Button, Badge, useColorModeValue, Spinner } from '@chakra-ui/react';
import { ChevronLeftIcon, ChevronRightIcon, EditIcon, DeleteIcon } from '@chakra-ui/icons';
import { format, addMonths, subMonths, startOfMonth, endOfMonth, eachDayOfInterval, isSameMonth, getDay, isSameDay } from 'date-fns';
import { ru } from 'date-fns/locale';
import { PostData } from '../types/types';

interface CalendarProps {
  posts: PostData[];
  onEditPost: (post: PostData) => void;
  onDeletePost: (post: PostData) => void;
  isLoading?: boolean;
}

const Calendar: React.FC<CalendarProps> = ({ posts, onEditPost, onDeletePost, isLoading = false }) => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const textColor = useColorModeValue('gray.800', 'white');
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const highlightColor = useColorModeValue('blue.50', 'blue.900');
  
  const nextMonth = () => setCurrentDate(addMonths(currentDate, 1));
  const prevMonth = () => setCurrentDate(subMonths(currentDate, 1));

  const monthStart = startOfMonth(currentDate);
  const monthEnd = endOfMonth(currentDate);
  const daysInMonth = eachDayOfInterval({ start: monthStart, end: monthEnd });
  
  // Получаем день недели первого дня месяца (0 - воскресенье, 1 - понедельник, ...)
  const startDay = getDay(monthStart);
  
  // Коррекция для начала недели с понедельника (в русской локализации)
  const startOffset = startDay === 0 ? 6 : startDay - 1;
  
  // Дни недели в русской локализации
  const daysOfWeek = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

  // Функция для получения постов на конкретный день
  const getPostsForDay = (day: Date) => {
    return posts.filter(post => {
      const postDate = new Date(post.target_date);
      return isSameDay(postDate, day);
    });
  };

  // Создаем сетку календаря
  const renderCalendarDays = () => {
    const calendarRows = [];
    let days = [];
    
    // Добавляем пустые ячейки для дней до начала месяца
    for (let i = 0; i < startOffset; i++) {
      days.push(
        <GridItem key={`empty-${i}`} p={2} borderWidth="1px" borderColor={borderColor}>
          <Box height="100px"></Box>
        </GridItem>
      );
    }
    
    // Добавляем дни месяца
    for (const day of daysInMonth) {
      const postsForDay = getPostsForDay(day);
      const isToday = isSameDay(day, new Date());
      
      days.push(
        <GridItem 
          key={day.toString()} 
          p={2} 
          borderWidth="1px" 
          borderColor={borderColor}
          bg={isToday ? highlightColor : bgColor}
        >
          <Text mb={2} fontWeight={isToday ? "bold" : "normal"}>
            {format(day, 'd')}
          </Text>
          
          <Box maxH="80px" overflowY="auto">
            {postsForDay.map(post => (
              <Flex 
                key={post.id} 
                p={1} 
                mb={1} 
                borderRadius="md" 
                bg="blue.100" 
                color="blue.800"
                justify="space-between"
                align="center"
                fontSize="xs"
              >
                <Text noOfLines={1} fontSize="xs" flex="1">
                  {post.topic_idea}
                </Text>
                <Flex>
                  <Button 
                    size="xs" 
                    variant="ghost" 
                    colorScheme="blue" 
                    onClick={() => onEditPost(post)}
                    p={1}
                    minW="auto"
                  >
                    <EditIcon boxSize={3} />
                  </Button>
                  <Button 
                    size="xs" 
                    variant="ghost" 
                    colorScheme="red" 
                    onClick={() => onDeletePost(post)}
                    p={1}
                    minW="auto"
                  >
                    <DeleteIcon boxSize={3} />
                  </Button>
                </Flex>
              </Flex>
            ))}
          </Box>
        </GridItem>
      );
      
      // Если достигли конца недели или последнего дня месяца, начинаем новую строку
      if ((days.length) % 7 === 0 || day.getTime() === monthEnd.getTime()) {
        // Если последняя неделя не полная, добавляем пустые ячейки
        if (day.getTime() === monthEnd.getTime() && days.length % 7 !== 0) {
          const remainingCells = 7 - (days.length % 7);
          for (let i = 0; i < remainingCells; i++) {
            days.push(
              <GridItem key={`empty-end-${i}`} p={2} borderWidth="1px" borderColor={borderColor}>
                <Box height="100px"></Box>
              </GridItem>
            );
          }
        }
        
        calendarRows.push(
          <Grid key={`row-${calendarRows.length}`} templateColumns="repeat(7, 1fr)">
            {days}
          </Grid>
        );
        days = [];
      }
    }
    
    return calendarRows;
  };

  return (
    <Box borderWidth="1px" borderRadius="lg" p={4} bg={bgColor} color={textColor}>
      <Flex justify="space-between" align="center" mb={4}>
        <Button onClick={prevMonth} size="sm" leftIcon={<ChevronLeftIcon />}>
          Пред.
        </Button>
        <Text fontSize="xl" fontWeight="bold">
          {format(currentDate, 'LLLL yyyy', { locale: ru })}
        </Text>
        <Button onClick={nextMonth} size="sm" rightIcon={<ChevronRightIcon />}>
          След.
        </Button>
      </Flex>
      
      {isLoading ? (
        <Flex justify="center" align="center" height="300px">
          <Spinner size="xl" color="blue.500" />
        </Flex>
      ) : (
        <Box>
          {/* Заголовки дней недели */}
          <Grid templateColumns="repeat(7, 1fr)" mb={2}>
            {daysOfWeek.map(day => (
              <GridItem key={day} textAlign="center" fontWeight="bold" p={2}>
                {day}
              </GridItem>
            ))}
          </Grid>
          
          {/* Дни месяца */}
          {renderCalendarDays()}
        </Box>
      )}
    </Box>
  );
};

export default Calendar; 